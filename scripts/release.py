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
/* Enable TinyUSB CDC-NCM class. The NCM interfaces are composited into
   MicroPython's static descriptor by patches applied in
   _patch_micropython_for_ncm() — see scripts/release.py. machine.USBDevice
   continues to manage runtime HID on top of MSC + NCM (its interface/EP
   allocator starts above USBD_ITF_BUILTIN_MAX / USBD_EP_BUILTIN_MAX, which
   the patch bumps to include the NCM interfaces and endpoints). */
#define CFG_TUD_NCM             (1)
#define CFG_TUD_NCM_EP_BUFSIZE  (64)
#define CFG_TUD_NCM_NTBSIZE     (3200)
"""

    header.write_text(base + (ncm_additions if ncm else ''), encoding='utf-8')
    return header


_NCM_TUSB_CONFIG_OLD = """\
/* Limits of builtin USB interfaces, endpoints, strings */
#if CFG_TUD_MSC
#define USBD_ITF_BUILTIN_MAX (USBD_ITF_MSC + 1)
#define USBD_STR_BUILTIN_MAX (USBD_STR_MSC + 1)
#define USBD_EP_BUILTIN_MAX (EPNUM_MSC_OUT + 1)"""

_NCM_TUSB_CONFIG_NEW = """\
/* pico-bit: NCM composited statically alongside MSC. NCM uses 2 interfaces
   (CDC comm + CDC data), 3 endpoints (notification + bulk in/out), 2 strings
   (interface label + MAC address). machine.USBDevice runtime HID slots into
   the next free interface/endpoint above BUILTIN_MAX. */
#if CFG_TUD_NCM
#define USBD_STR_NCM (USBD_STR_MSC + 1)
#define USBD_STR_NCM_MAC (USBD_STR_NCM + 1)
#define USBD_ITF_NCM_COMM (USBD_ITF_MSC + 1)
#define USBD_ITF_NCM_DATA (USBD_ITF_NCM_COMM + 1)
#define EPNUM_NCM_NOTIF (0x82)
#define EPNUM_NCM_OUT   (0x03)
#define EPNUM_NCM_IN    (0x83)
#endif

/* Limits of builtin USB interfaces, endpoints, strings */
#if CFG_TUD_MSC && CFG_TUD_NCM
#define USBD_ITF_BUILTIN_MAX (USBD_ITF_NCM_DATA + 1)
#define USBD_STR_BUILTIN_MAX (USBD_STR_NCM_MAC + 1)
#define USBD_EP_BUILTIN_MAX  (EPNUM_NCM_OUT + 1)
#elif CFG_TUD_MSC
#define USBD_ITF_BUILTIN_MAX (USBD_ITF_MSC + 1)
#define USBD_STR_BUILTIN_MAX (USBD_STR_MSC + 1)
#define USBD_EP_BUILTIN_MAX (EPNUM_MSC_OUT + 1)"""

_NCM_DESC_LEN_OLD = """\
#define MP_USBD_BUILTIN_DESC_CFG_LEN (TUD_CONFIG_DESC_LEN +                     \\
    (CFG_TUD_CDC ? (TUD_CDC_DESC_LEN) : 0) +  \\
    (CFG_TUD_MSC ? (TUD_MSC_DESC_LEN) : 0)    \\
    )"""

_NCM_DESC_LEN_NEW = """\
#define MP_USBD_BUILTIN_DESC_CFG_LEN (TUD_CONFIG_DESC_LEN +                     \\
    (CFG_TUD_CDC ? (TUD_CDC_DESC_LEN) : 0) +  \\
    (CFG_TUD_MSC ? (TUD_MSC_DESC_LEN) : 0) +  \\
    (CFG_TUD_NCM ? (TUD_CDC_NCM_DESC_LEN) : 0) \\
    )"""

# Anchor strings must match MicroPython source verbatim — don't reflow.
_NCM_DESC_ARRAY_OLD = """\
    #if CFG_TUD_MSC
    TUD_MSC_DESCRIPTOR(USBD_ITF_MSC, USBD_STR_MSC, EPNUM_MSC_OUT, EPNUM_MSC_IN, USBD_MSC_IN_OUT_MAX_SIZE),
    #endif
};"""  # noqa: E501

_NCM_DESC_ARRAY_NEW = """\
    #if CFG_TUD_MSC
    TUD_MSC_DESCRIPTOR(USBD_ITF_MSC, USBD_STR_MSC, EPNUM_MSC_OUT, EPNUM_MSC_IN, USBD_MSC_IN_OUT_MAX_SIZE),
    #endif
    #if CFG_TUD_NCM
    TUD_CDC_NCM_DESCRIPTOR(USBD_ITF_NCM_COMM, USBD_STR_NCM, USBD_STR_NCM_MAC,
        EPNUM_NCM_NOTIF, 8, EPNUM_NCM_OUT, EPNUM_NCM_IN, 64, CFG_TUD_NCM_NTBSIZE),
    #endif
};"""  # noqa: E501

_NCM_STR_OLD = """\
            #if CFG_TUD_MSC
            case USBD_STR_MSC:
                desc_str = MICROPY_HW_USB_MSC_INTERFACE_STRING;
                break;
            #endif"""

_NCM_STR_NEW = """\
            #if CFG_TUD_MSC
            case USBD_STR_MSC:
                desc_str = MICROPY_HW_USB_MSC_INTERFACE_STRING;
                break;
            #endif
            #if CFG_TUD_NCM
            case USBD_STR_NCM:
                desc_str = "Pico Bit NCM";
                break;
            case USBD_STR_NCM_MAC: {
                extern uint8_t tud_network_mac_address[6];
                static char _ncm_mac_str[13];
                static const char _hex[] = "0123456789ABCDEF";
                for (int i = 0; i < 6; i++) {
                    _ncm_mac_str[i * 2] = _hex[(tud_network_mac_address[i] >> 4) & 0xF];
                    _ncm_mac_str[i * 2 + 1] = _hex[tud_network_mac_address[i] & 0xF];
                }
                _ncm_mac_str[12] = 0;
                desc_str = _ncm_mac_str;
                break;
            }
            #endif"""


def _patch_micropython_for_ncm() -> None:
    """Patch MicroPython's static USB descriptor to include CDC-NCM alongside MSC.

    Three files are touched:
      * shared/tinyusb/tusb_config.h     — NCM interface/endpoint/string defines
                                            and BUILTIN_MAX expansion.
      * shared/tinyusb/mp_usbd.h         — descriptor length macro extension.
      * shared/tinyusb/mp_usbd_descriptor.c — NCM descriptor entry + MAC string.

    Each patch is idempotent: the new content is only written if the old form
    is still present in the file. This keeps standard builds (CFG_TUD_NCM=0)
    behaviorally unchanged because every patched section is wrapped in
    `#if CFG_TUD_NCM`.
    """
    _replace_once(
        MICROPYTHON_DIR / 'shared' / 'tinyusb' / 'tusb_config.h',
        _NCM_TUSB_CONFIG_OLD,
        _NCM_TUSB_CONFIG_NEW,
    )
    _replace_once(
        MICROPYTHON_DIR / 'shared' / 'tinyusb' / 'mp_usbd.h',
        _NCM_DESC_LEN_OLD,
        _NCM_DESC_LEN_NEW,
    )
    descriptor = MICROPYTHON_DIR / 'shared' / 'tinyusb' / 'mp_usbd_descriptor.c'
    _replace_once(descriptor, _NCM_DESC_ARRAY_OLD, _NCM_DESC_ARRAY_NEW)
    _replace_once(descriptor, _NCM_STR_OLD, _NCM_STR_NEW)


def _replace_once(path: Path, old: str, new: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f'expected file for NCM patch: {path}')
    content = path.read_text(encoding='utf-8')
    if new in content:
        return
    if old not in content:
        raise RuntimeError(
            f'NCM patch anchor missing in {path.relative_to(MICROPYTHON_DIR)} — '
            'MicroPython source may have changed shape; update _NCM_*_OLD constants.'
        )
    path.write_text(content.replace(old, new, 1), encoding='utf-8')


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

    # NCM uses a separate build directory so cmake re-runs fresh and picks up
    # USER_C_MODULES. Reusing build-{board} would skip cmake re-config when the
    # standard build has already created that directory's Makefile, and the
    # NCM sources would never get compiled into firmware.
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
    if ncm:
        make_args.append(f'USER_C_MODULES={ROOT / "c_modules" / "micropython.cmake"}')

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
