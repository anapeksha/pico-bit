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

# USB device identity profiles. Each profile sets the OS-visible strings
# (iManufacturer, iProduct, MSC SCSI inquiry, filesystem label) to control
# what name shows up in Device Manager / System Information / `lsusb`. The
# "default" profile keeps pico-bit branding for development. Other profiles
# strip the branding to a neutral identity without impersonating a registered
# vendor (USB-IF agreement violation territory).
#
# VID/PID stay at the chip's legitimate Raspberry Pi default for every
# profile except `hobbyist`, which switches to Objective Development's
# V-USB shared VID/PID range — licensed by OD for non-commercial use, see
# https://www.obdev.at/products/vusb/license.html. Overriding VID/PID on
# Windows forces a fresh driver install on first plug, so most engagements
# stick with the default VID and only override the strings.
USB_IDENTITY_PROFILES: dict[str, dict[str, object]] = {
    'default': {
        'manufacturer': 'Pico Bit',
        'product': 'Pico Bit',
        'msc_interface': 'Pico Bit MSC',
        'msc_vendor': 'PICOBIT',
        'msc_product': 'PICO-BIT',
        'fs_label': 'PICO-BIT',
    },
    'generic-composite': {
        'manufacturer': 'USB',
        'product': 'USB Composite Device',
        'msc_interface': 'USB Mass Storage',
        'msc_vendor': 'USB',
        'msc_product': 'Mass Storage',
        'fs_label': 'USB-DRIVE',
    },
    'generic-keyboard': {
        'manufacturer': 'USB',
        'product': 'USB Keyboard',
        'msc_interface': 'Keyboard Storage',
        'msc_vendor': 'USB',
        'msc_product': 'Keyboard FS',
        'fs_label': 'KBD-FS',
    },
    'hobbyist': {
        'vid': 0x16C0,
        'pid': 0x05DC,
        'manufacturer': 'Generic',
        'product': 'HID Composite Device',
        'msc_interface': 'HID Storage',
        'msc_vendor': 'Generic',
        'msc_product': 'HID Storage',
        'fs_label': 'HID-DRIVE',
    },
}
DEFAULT_USB_PROFILE = 'default'


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


def release_filename(board: str, artifact_version: str | None) -> str:
    if artifact_version:
        return f'pico-bit-{board}-{artifact_version}.uf2'
    return f'pico-bit-{board}.uf2'


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


def resolve_usb_profile(name: str | None) -> dict[str, object]:
    """Look up a USB identity profile by name. Raises ValueError on unknown."""
    key = (name or DEFAULT_USB_PROFILE).strip().lower()
    if key not in USB_IDENTITY_PROFILES:
        raise ValueError(
            f'unknown USB profile {name!r}; choose from {", ".join(sorted(USB_IDENTITY_PROFILES))}'
        )
    return USB_IDENTITY_PROFILES[key]


def write_usb_config_header(profile_name: str = DEFAULT_USB_PROFILE) -> Path:
    """Render .build/pico_bit_usb_config.h with the chosen identity profile.

    The header is force-included into MicroPython's compilation via
    CFLAGS_EXTRA in build_firmware, so the macros land before tusb_config.h
    and mp_usbd_descriptor.c can see them.
    """
    profile = resolve_usb_profile(profile_name)
    header = ROOT / '.build' / 'pico_bit_usb_config.h'
    header.parent.mkdir(parents=True, exist_ok=True)

    lines = ['#pragma once', '']
    string_defines = (
        ('MICROPY_HW_FLASH_FS_LABEL', profile['fs_label']),
        ('MICROPY_HW_USB_MANUFACTURER_STRING', profile['manufacturer']),
        ('MICROPY_HW_USB_PRODUCT_FS_STRING', profile['product']),
        ('MICROPY_HW_USB_MSC_INTERFACE_STRING', profile['msc_interface']),
        ('MICROPY_HW_USB_MSC_INQUIRY_VENDOR_STRING', profile['msc_vendor']),
        ('MICROPY_HW_USB_MSC_INQUIRY_PRODUCT_STRING', profile['msc_product']),
        ('MICROPY_HW_USB_MSC_INQUIRY_REVISION_STRING', '1.0'),
    )
    for macro, value in string_defines:
        lines.append(f'#undef {macro}')
        lines.append(f'#define {macro} "{value}"')
        lines.append('')

    # VID/PID overrides only emitted when the profile sets them — otherwise the
    # board's MicroPython default (Raspberry Pi VID 0x2E8A + board-specific PID)
    # is used, which avoids Windows driver re-install on first plug.
    if 'vid' in profile:
        lines.append('#undef MICROPY_HW_USB_VID')
        lines.append(f'#define MICROPY_HW_USB_VID ({profile["vid"]:#06x})')
        lines.append('#undef MICROPY_HW_USB_PID')
        lines.append(f'#define MICROPY_HW_USB_PID ({profile["pid"]:#06x})')
        lines.append('')

    header.write_text('\n'.join(lines), encoding='utf-8')
    return header


def build_firmware(
    board: str,
    ref: str,
    overrides: dict[str, OverrideValue],
    artifact_version: str | None,
    *,
    usb_profile: str = DEFAULT_USB_PROFILE,
) -> Path:
    usb_config_header = write_usb_config_header(usb_profile)

    _run(
        [
            'make',
            '-C',
            'ports/rp2',
            f'BOARD={board}',
            f'FROZEN_MANIFEST={MANIFEST}',
            'MICROPY_PY_BLUETOOTH=0',
            'MICROPY_BLUETOOTH_NIMBLE=0',
            (
                'CFLAGS_EXTRA='
                '-DMICROPY_HW_USB_CDC=0 '
                '-DMICROPY_HW_USB_MSC=1 '
                f'-include {usb_config_header}'
            ),
        ],
        cwd=MICROPYTHON_DIR,
    )
    firmware = MICROPYTHON_DIR / 'ports' / 'rp2' / f'build-{board}' / 'firmware.uf2'
    if not firmware.exists():
        raise FileNotFoundError(f'Expected firmware at {firmware}')

    DIST_DIR.mkdir(exist_ok=True)
    release_name = release_filename(board, artifact_version)
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
        'usb_profile': usb_profile,
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
    parser.add_argument(
        '--usb-profile',
        default=DEFAULT_USB_PROFILE,
        choices=sorted(USB_IDENTITY_PROFILES),
        help=(
            'USB device identity profile. "default" keeps Pico Bit branding for '
            'development; "generic-composite" / "generic-keyboard" strip branding '
            'without impersonating a registered vendor; "hobbyist" additionally '
            'switches VID/PID to the V-USB shared range (non-commercial use only).'
        ),
    )
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
    build_firmware(
        args.board,
        args.micropython_ref,
        overrides,
        artifact_version,
        usb_profile=args.usb_profile,
    )
    return 0
