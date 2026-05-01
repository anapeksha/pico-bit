from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_build_cleans_dist_to_single_boot_file() -> None:
    root = Path(__file__).resolve().parents[1]
    dist = root / 'dist'
    stale = dist / 'stale.bin'
    dist.mkdir(exist_ok=True)
    stale.write_bytes(b'x')

    subprocess.run([sys.executable, 'build.py'], cwd=root, check=True)

    assert not stale.exists()
    assert sorted(path.name for path in dist.iterdir()) == ['boot.py']


def test_build_injects_runtime_config_overrides() -> None:
    root = Path(__file__).resolve().parents[1]
    dist = root / 'dist'

    subprocess.run(
        [
            sys.executable,
            'build.py',
            '--ap-ssid',
            'Studio Pico',
            '--ap-password',
            'keyboard42',
            '--allow-unsafe',
            'true',
        ],
        cwd=root,
        check=True,
    )

    bundled = (dist / 'boot.py').read_text(encoding='utf-8')
    assert "AP_SSID: str = 'Studio Pico'" in bundled
    assert "AP_PASSWORD: str = 'keyboard42'" in bundled
    assert 'ALLOW_UNSAFE: bool = True' in bundled


def test_build_emits_ruff_clean_bundle() -> None:
    root = Path(__file__).resolve().parents[1]

    subprocess.run([sys.executable, 'build.py'], cwd=root, check=True)
    subprocess.run(
        [sys.executable, '-m', 'ruff', 'format', '--check', 'dist/boot.py'],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [sys.executable, '-m', 'ruff', 'check', 'dist/boot.py'],
        cwd=root,
        check=True,
    )
