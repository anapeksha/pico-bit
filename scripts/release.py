#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

from .asset_pipeline import sync_web_assets
from .build_pipeline import (
    OverrideValue,
    build_config_overrides,
    build_module_overrides,
    build_mpy_tree,
    prepare_source_tree,
)

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / 'src'
DIST_DIR = ROOT / 'dist'
MPY_DIR = DIST_DIR / 'mpy'
BUILD_DIR = ROOT / '.build'
MICROPYTHON_DIR = BUILD_DIR / 'micropython'
MANIFEST = ROOT / 'frozen' / 'manifest.py'
DEFAULT_BOARD = 'RPI_PICO2_W'
DEFAULT_MICROPYTHON_REF = 'v1.28.0'
DEFAULT_REPO = 'https://github.com/micropython/micropython.git'
PYPROJECT = ROOT / 'pyproject.toml'
RELEASE_JSON = DIST_DIR / 'release.json'
ASSET_PATTERNS = ('*.uf2', 'payloads-*.zip')


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def _ensure_micropython_checkout(repo_url: str, ref: str) -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    if not MICROPYTHON_DIR.exists():
        _run(['git', 'clone', '--branch', ref, '--depth', '1', repo_url, str(MICROPYTHON_DIR)])
    else:
        _run(
            ['git', '-c', 'fetch.recurseSubmodules=false', 'fetch', '--tags', '--force', 'origin'],
            cwd=MICROPYTHON_DIR,
        )
        _run(['git', 'checkout', ref], cwd=MICROPYTHON_DIR)
    _run(['git', 'submodule', 'update', '--init', '--recursive'], cwd=MICROPYTHON_DIR)


def _build_repo_mpy_cross() -> Path:
    _run(['make', '-C', 'mpy-cross'], cwd=MICROPYTHON_DIR)
    return MICROPYTHON_DIR / 'mpy-cross' / 'build' / 'mpy-cross'


def pyproject_version(pyproject_path: Path = PYPROJECT) -> str | None:
    if not pyproject_path.exists():
        return None

    data = tomllib.loads(pyproject_path.read_text(encoding='utf-8'))
    version = data.get('tool', {}).get('poetry', {}).get('version')
    if not isinstance(version, str):
        return None

    version = version.strip()
    return version or None


def resolve_artifact_version(
    release_version: str | None,
    pyproject_path: Path = PYPROJECT,
) -> str | None:
    if release_version is not None:
        release_version = release_version.strip()
        if release_version:
            return release_version
    return pyproject_version(pyproject_path)


def release_filename(board: str, artifact_version: str | None, *, ncm: bool = False) -> str:
    suffix = '-ncm' if ncm else ''
    if artifact_version:
        return f'pico-bit-{board}{suffix}-{artifact_version}.uf2'
    return f'pico-bit-{board}{suffix}.uf2'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def collect_release_assets(dist_dir: Path = DIST_DIR) -> list[dict[str, object]]:
    assets: list[dict[str, object]] = []
    for pattern in ASSET_PATTERNS:
        for path in sorted(dist_dir.glob(pattern)):
            kind = 'firmware' if path.suffix == '.uf2' else 'bundle'
            assets.append(
                {
                    'kind': kind,
                    'name': path.name,
                    'sha256': sha256_file(path),
                    'size_bytes': path.stat().st_size,
                }
            )
    return assets


def refresh_release_metadata(release_json: Path = RELEASE_JSON) -> dict[str, object]:
    metadata = json.loads(release_json.read_text(encoding='utf-8')) if release_json.exists() else {}
    assets = collect_release_assets(release_json.parent)
    metadata['assets'] = assets

    firmware_name = next(
        (asset['name'] for asset in assets if asset.get('kind') == 'firmware'),
        None,
    )
    if firmware_name is not None:
        metadata['firmware'] = firmware_name
        firmware_sha = next(
            (
                asset['sha256']
                for asset in assets
                if asset.get('kind') == 'firmware' and asset.get('name') == firmware_name
            ),
            None,
        )
        if firmware_sha is not None:
            metadata['firmware_sha256'] = firmware_sha

    release_json.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


def write_usb_config_header(*, ncm: bool = False) -> Path:
    header = ROOT / '.build' / 'pico_bit_usb_config.h'
    header.parent.mkdir(parents=True, exist_ok=True)

    base = """
#pragma once

#undef MICROPY_HW_FLASH_FS_LABEL
#define MICROPY_HW_FLASH_FS_LABEL "PICO-BIT"

#undef MICROPY_HW_USB_MANUFACTURER_STRING
#define MICROPY_HW_USB_MANUFACTURER_STRING "Pico Bit"

#undef MICROPY_HW_USB_PRODUCT_FS_STRING
#define MICROPY_HW_USB_PRODUCT_FS_STRING "Pico Bit"

#undef MICROPY_HW_USB_MSC_INTERFACE_STRING
#define MICROPY_HW_USB_MSC_INTERFACE_STRING "Pico Bit MSC"

#undef MICROPY_HW_USB_MSC_INQUIRY_VENDOR_STRING
#define MICROPY_HW_USB_MSC_INQUIRY_VENDOR_STRING "PICOBIT"

#undef MICROPY_HW_USB_MSC_INQUIRY_PRODUCT_STRING
#define MICROPY_HW_USB_MSC_INQUIRY_PRODUCT_STRING "PICO-BIT"

#undef MICROPY_HW_USB_MSC_INQUIRY_REVISION_STRING
#define MICROPY_HW_USB_MSC_INQUIRY_REVISION_STRING "1.0"
""".lstrip()

    ncm_additions = """
/* CDC-NCM additions: fence EP3/EP4 away from machine.USBDevice runtime allocator
   so the NCM C module can claim them before HID enumeration. */
#undef  USBD_EP_BUILTIN_MAX
#define USBD_EP_BUILTIN_MAX     (5)

#define CFG_TUD_NCM             (1)
#define CFG_TUD_NCM_EP_BUFSIZE  (64)
#define CFG_TUD_NCM_NTBSIZE     (3200)
"""

    header.write_text(base + (ncm_additions if ncm else ''), encoding='utf-8')
    return header


def _patch_micropython_for_ncm() -> None:
    # 1. Guard USBD_EP_BUILTIN_MAX in tusb_config.h so our -include header
    #    can override it without triggering -Werror=macro-redefined.
    tusb_config = MICROPYTHON_DIR / 'shared' / 'tinyusb' / 'tusb_config.h'
    if tusb_config.exists():
        content = tusb_config.read_text(encoding='utf-8')
        old = '#define USBD_EP_BUILTIN_MAX (EPNUM_MSC_OUT + 1)'
        new = '#ifndef USBD_EP_BUILTIN_MAX\n#define USBD_EP_BUILTIN_MAX (EPNUM_MSC_OUT + 1)\n#endif'
        if old in content and new not in content:
            tusb_config.write_text(content.replace(old, new), encoding='utf-8')

    # 2. Add NCM C sources directly to ports/rp2/CMakeLists.txt.
    #    CMakeLists.txt is a tracked cmake input, so any edit to it causes
    #    cmake to automatically re-run before the next build — this is more
    #    reliable than USER_C_MODULES discovery, which depends on cmake cache
    #    state from prior build directory reuse.
    cmakelists = MICROPYTHON_DIR / 'ports' / 'rp2' / 'CMakeLists.txt'
    if not cmakelists.exists():
        return
    sentinel = '# pico-bit-ncm-sources'
    content = cmakelists.read_text(encoding='utf-8')
    if sentinel in content:
        return
    ncm_src = ROOT / 'c_modules' / 'usb_ncm'
    addition = f"""
{sentinel}
if(TARGET firmware)
    target_sources(firmware PRIVATE
        "{ncm_src / 'usb_ncm.c'}"
        "{ncm_src / 'usb_ncm_descriptors.c'}"
    )
    target_include_directories(firmware PRIVATE "{ncm_src}")
endif()
"""
    cmakelists.write_text(content + addition, encoding='utf-8')


def build_firmware(
    board: str,
    ref: str,
    overrides: dict[str, OverrideValue],
    artifact_version: str | None,
    *,
    ncm: bool = False,
) -> Path:
    usb_config_header = write_usb_config_header(ncm=ncm)
    if ncm:
        _patch_micropython_for_ncm()

    # NCM uses a separate build directory so cmake always runs fresh.
    # Reusing build-{board} would skip cmake re-config when the standard
    # build has already created that directory's Makefile.
    build_dir = f'build-{board}' + ('-ncm' if ncm else '')

    make_args = [
        'make',
        '-C',
        'ports/rp2',
        f'BOARD={board}',
        f'BUILD={build_dir}',
        f'FROZEN_MANIFEST={MANIFEST}',
        'MICROPY_PY_BLUETOOTH=0',
        'MICROPY_BLUETOOTH_NIMBLE=0',
        (
            'CFLAGS_EXTRA='
            '-DMICROPY_HW_USB_CDC=0 '
            '-DMICROPY_HW_USB_MSC=1 '
            f'-include {usb_config_header}'
        ),
    ]

    _run(make_args, cwd=MICROPYTHON_DIR)

    firmware = MICROPYTHON_DIR / 'ports' / 'rp2' / build_dir / 'firmware.uf2'
    if not firmware.exists():
        raise FileNotFoundError(f'Expected firmware at {firmware}')

    DIST_DIR.mkdir(exist_ok=True)
    release_name = release_filename(board, artifact_version, ncm=ncm)
    output = DIST_DIR / release_name
    output.write_bytes(firmware.read_bytes())

    metadata: dict[str, object] = {
        'artifact_version': artifact_version,
        'board': board,
        'config_overrides': overrides,
        'firmware': release_name,
        'manifest': str(MANIFEST),
        'micropython_ref': ref,
        'module_count': len(list(MPY_DIR.rglob('*.mpy'))),
        'usb_msc_enabled': True,
        'usb_ncm_enabled': ncm,
    }
    RELEASE_JSON.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    refresh_release_metadata(RELEASE_JSON)
    return output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Package frozen Pico Bit firmware artifacts.')
    parser.add_argument(
        'command',
        nargs='?',
        default='build-uf2',
        choices=['build-uf2', 'refresh-release-json', 'sync-assets'],
    )
    parser.add_argument('--board', default=DEFAULT_BOARD)
    parser.add_argument('--micropython-ref', default=DEFAULT_MICROPYTHON_REF)
    parser.add_argument('--repo-url', default=DEFAULT_REPO)
    parser.add_argument('--ap-ssid')
    parser.add_argument('--ap-password')
    parser.add_argument('--portal-auth-enabled')
    parser.add_argument('--portal-username')
    parser.add_argument('--portal-password')
    parser.add_argument('--cors-allowed-origin')
    parser.add_argument('--cors-allow-credentials')
    parser.add_argument('--release-version')
    parser.add_argument('--usb-ncm', action='store_true', default=False)
    return parser


def run_release(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == 'sync-assets':
        sync_web_assets()
        return 0

    if args.command == 'refresh-release-json':
        refresh_release_metadata(RELEASE_JSON)
        return 0

    try:
        overrides = build_config_overrides(args)
    except ValueError as exc:
        parser.error(str(exc))

    if args.usb_ncm:
        overrides['USB_NCM_ENABLED'] = True

    _ensure_micropython_checkout(args.repo_url, args.micropython_ref)
    mpy_cross = _build_repo_mpy_cross()
    module_overrides = build_module_overrides(
        ROOT,
        device_config_overrides=overrides,
    )
    artifact_version = resolve_artifact_version(args.release_version)
    source_dir = prepare_source_tree(
        build_dir=BUILD_DIR,
        root_src_dir=SRC_DIR,
        overrides_by_module=module_overrides,
    )
    build_mpy_tree(
        compiler_cmd=[str(mpy_cross)],
        output_dir=MPY_DIR,
        source_dir=source_dir,
        cwd=ROOT,
    )
    build_firmware(args.board, args.micropython_ref, overrides, artifact_version, ncm=args.usb_ncm)
    return 0
