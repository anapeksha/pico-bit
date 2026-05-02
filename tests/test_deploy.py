from __future__ import annotations

import importlib
import sys
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BUILD_SUPPORT = importlib.import_module('scripts.build_support')
DEPLOY = importlib.import_module('scripts.deploy')


def _args(**overrides) -> Namespace:
    values = {
        'allow_unsafe': None,
        'ap_password': None,
        'ap_ssid': None,
        'board': 'RPI_PICO2_W',
        'command': 'build-uf2',
        'cors_allow_credentials': None,
        'cors_allowed_origin': None,
        'micropython_ref': DEPLOY.DEFAULT_MICROPYTHON_REF,
        'portal_auth_enabled': None,
        'portal_password': None,
        'portal_username': None,
        'repo_url': DEPLOY.DEFAULT_REPO,
    }
    values.update(overrides)
    return Namespace(**values)


def test_build_config_overrides_supports_release_flags() -> None:
    overrides = DEPLOY.build_config_overrides(
        _args(
            allow_unsafe='true',
            ap_password='keyboard42',
            ap_ssid='Studio Pico',
            cors_allow_credentials='true',
            cors_allowed_origin='https://example.com',
            portal_auth_enabled='false',
            portal_password='injector42',
            portal_username='pico',
        )
    )

    assert overrides == {
        'ALLOW_UNSAFE': True,
        'AP_PASSWORD': 'keyboard42',
        'AP_SSID': 'Studio Pico',
        'CORS_ALLOW_CREDENTIALS': True,
        'CORS_ALLOWED_ORIGIN': 'https://example.com',
        'PORTAL_AUTH_ENABLED': False,
        'PORTAL_PASSWORD': 'injector42',
        'PORTAL_USERNAME': 'pico',
    }


def test_build_config_overrides_omits_default_boolean_requests() -> None:
    overrides = DEPLOY.build_config_overrides(
        _args(
            allow_unsafe='default',
            portal_auth_enabled='default',
            cors_allow_credentials='default',
        )
    )

    assert overrides == {}


def test_render_device_config_preserves_derived_portal_password() -> None:
    source = (ROOT / 'src' / 'device_config.py').read_text(encoding='utf-8')

    rendered = BUILD_SUPPORT.render_device_config(source, {'AP_PASSWORD': 'keyboard42'})

    assert "AP_PASSWORD: str = 'keyboard42'" in rendered
    assert 'PORTAL_PASSWORD: str = AP_PASSWORD' in rendered


def test_render_device_config_can_override_portal_login_values() -> None:
    source = (ROOT / 'src' / 'device_config.py').read_text(encoding='utf-8')

    rendered = BUILD_SUPPORT.render_device_config(
        source,
        {
            'PORTAL_AUTH_ENABLED': False,
            'PORTAL_PASSWORD': 'injector42',
            'PORTAL_USERNAME': 'pico',
        },
    )

    assert 'PORTAL_AUTH_ENABLED: bool = False' in rendered
    assert "PORTAL_USERNAME: str = 'pico'" in rendered
    assert "PORTAL_PASSWORD: str = 'injector42'" in rendered


def test_build_mpy_tree_embeds_relative_source_names(tmp_path, monkeypatch) -> None:
    source_dir = tmp_path / 'src'
    output_dir = tmp_path / 'mpy'
    compiler_calls: list[list[str]] = []

    boot = source_dir / 'boot.py'
    server = source_dir / 'server.py'
    parser = source_dir / 'ducky' / 'parser.py'
    server.parent.mkdir(parents=True, exist_ok=True)
    parser.parent.mkdir(parents=True, exist_ok=True)
    boot.write_text('import main\n', encoding='utf-8')
    server.write_text('VALUE = 1\n', encoding='utf-8')
    parser.write_text('VALUE = 2\n', encoding='utf-8')

    def fake_run(cmd: list[str], *, cwd: Path, check: bool) -> None:
        assert check is True
        assert cwd == ROOT
        compiler_calls.append(cmd)
        output = Path(cmd[cmd.index('-o') + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'mpy')

    monkeypatch.setattr(BUILD_SUPPORT.subprocess, 'run', fake_run)

    compiled = BUILD_SUPPORT.build_mpy_tree(
        compiler_cmd=['mpy-cross'],
        output_dir=output_dir,
        source_dir=source_dir,
        cwd=ROOT,
    )

    assert [path.relative_to(output_dir).as_posix() for path in compiled] == [
        'boot.mpy',
        'ducky/parser.mpy',
        'server.mpy',
    ]
    assert [call[call.index('-s') + 1] for call in compiler_calls] == [
        'boot.py',
        'ducky/parser.py',
        'server.py',
    ]
