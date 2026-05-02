from __future__ import annotations

import sys
from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SPEC = spec_from_file_location('deploy', ROOT / 'deploy.py')
assert SPEC is not None and SPEC.loader is not None
DEPLOY = module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)
BUILD_SUPPORT_SPEC = spec_from_file_location('build_support', ROOT / 'build_support.py')
assert BUILD_SUPPORT_SPEC is not None and BUILD_SUPPORT_SPEC.loader is not None
BUILD_SUPPORT = module_from_spec(BUILD_SUPPORT_SPEC)
BUILD_SUPPORT_SPEC.loader.exec_module(BUILD_SUPPORT)


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
