#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from pathlib import Path

from .asset_pipeline import sync_web_assets
from .build_support import (
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


def build_firmware(
    board: str,
    ref: str,
    overrides: dict[str, OverrideValue],
    artifact_version: str | None,
) -> Path:
    _run(
        [
            'make',
            '-C',
            'ports/rp2',
            f'BOARD={board}',
            f'FROZEN_MANIFEST={MANIFEST}',
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

    metadata = {
        'artifact_version': artifact_version,
        'board': board,
        'config_overrides': overrides,
        'firmware': release_name,
        'manifest': str(MANIFEST),
        'micropython_ref': ref,
        'module_count': len(list(MPY_DIR.rglob('*.mpy'))),
    }
    (DIST_DIR / 'release.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Package frozen Pico Bit firmware artifacts.')
    parser.add_argument(
        'command',
        nargs='?',
        default='build-uf2',
        choices=['build-uf2', 'sync-assets'],
    )
    parser.add_argument('--board', default=DEFAULT_BOARD)
    parser.add_argument('--micropython-ref', default=DEFAULT_MICROPYTHON_REF)
    parser.add_argument('--repo-url', default=DEFAULT_REPO)
    parser.add_argument('--ap-ssid')
    parser.add_argument('--ap-password')
    parser.add_argument('--allow-unsafe')
    parser.add_argument('--portal-auth-enabled')
    parser.add_argument('--portal-username')
    parser.add_argument('--portal-password')
    parser.add_argument('--cors-allowed-origin')
    parser.add_argument('--cors-allow-credentials')
    parser.add_argument('--release-version')
    return parser


def run_deploy(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == 'sync-assets':
        sync_web_assets()
        return 0

    try:
        overrides = build_config_overrides(args)
    except ValueError as exc:
        parser.error(str(exc))

    _ensure_micropython_checkout(args.repo_url, args.micropython_ref)
    mpy_cross = _build_repo_mpy_cross()
    module_overrides = build_module_overrides(
        ROOT,
        build_dir=BUILD_DIR,
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
    build_firmware(args.board, args.micropython_ref, overrides, artifact_version)
    return 0
