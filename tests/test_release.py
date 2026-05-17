from __future__ import annotations

import importlib
import json
import sys
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BUILD_PIPELINE = importlib.import_module('scripts.build_pipeline')
RELEASE = importlib.import_module('scripts.release')


def _args(**overrides) -> Namespace:
    values = {
        'ap_password': None,
        'ap_ssid': None,
        'board': 'RPI_PICO2_W',
        'command': 'build-uf2',
        'cors_allow_credentials': None,
        'cors_allowed_origin': None,
        'micropython_ref': RELEASE.DEFAULT_MICROPYTHON_REF,
        'portal_auth_enabled': None,
        'portal_password': None,
        'portal_username': None,
        'repo_url': RELEASE.DEFAULT_REPO,
    }
    values.update(overrides)
    return Namespace(**values)


def test_build_config_overrides_supports_release_flags() -> None:
    overrides = BUILD_PIPELINE.build_config_overrides(
        _args(
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
        'AP_PASSWORD': 'keyboard42',
        'AP_SSID': 'Studio Pico',
        'CORS_ALLOW_CREDENTIALS': True,
        'CORS_ALLOWED_ORIGIN': 'https://example.com',
        'PORTAL_AUTH_ENABLED': False,
        'PORTAL_PASSWORD': 'injector42',
        'PORTAL_USERNAME': 'pico',
    }


def test_build_config_overrides_omits_default_boolean_requests() -> None:
    overrides = BUILD_PIPELINE.build_config_overrides(
        _args(
            portal_auth_enabled='default',
            cors_allow_credentials='default',
        )
    )

    assert overrides == {}


def test_resolve_artifact_version_prefers_explicit_release_tag(tmp_path) -> None:
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text('[tool.poetry]\nversion = "0.0.1"\n', encoding='utf-8')

    version = RELEASE.resolve_artifact_version('v1.2.3', pyproject)

    assert version == 'v1.2.3'


def test_resolve_artifact_version_falls_back_to_pyproject(tmp_path) -> None:
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text('[tool.poetry]\nversion = "0.0.1"\n', encoding='utf-8')

    version = RELEASE.resolve_artifact_version(None, pyproject)

    assert version == '0.0.1'


def test_resolve_artifact_version_can_skip_suffix_when_unavailable(tmp_path) -> None:
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text('[tool.poetry]\nname = "pico-bit"\n', encoding='utf-8')

    version = RELEASE.resolve_artifact_version('', pyproject)

    assert version is None


def test_release_filename_uses_optional_version_suffix() -> None:
    assert RELEASE.release_filename('RPI_PICO2_W', 'v1.2.3') == 'pico-bit-RPI_PICO2_W-v1.2.3.uf2'
    assert RELEASE.release_filename('RPI_PICO2_W', None) == 'pico-bit-RPI_PICO2_W.uf2'


def test_collect_release_assets_includes_sha256_and_size(tmp_path) -> None:
    firmware = tmp_path / 'pico-bit-RPI_PICO2_W-v1.2.3.uf2'
    linux_zip = tmp_path / 'payloads-linux.zip'
    firmware.write_bytes(b'firmware-bytes')
    linux_zip.write_bytes(b'zip-bytes')

    assets = RELEASE.collect_release_assets(tmp_path)

    assert assets == [
        {
            'kind': 'firmware',
            'name': firmware.name,
            'sha256': RELEASE.sha256_file(firmware),
            'size_bytes': len(b'firmware-bytes'),
        },
        {
            'kind': 'bundle',
            'name': linux_zip.name,
            'sha256': RELEASE.sha256_file(linux_zip),
            'size_bytes': len(b'zip-bytes'),
        },
    ]


def test_refresh_release_metadata_merges_asset_checksums(tmp_path) -> None:
    firmware = tmp_path / 'pico-bit-RPI_PICO2_W-v1.2.3.uf2'
    windows_zip = tmp_path / 'payloads-windows.zip'
    firmware.write_bytes(b'firmware')
    windows_zip.write_bytes(b'windows-zip')
    release_json = tmp_path / 'release.json'
    release_json.write_text(
        '{"board": "RPI_PICO2_W", "artifact_version": "v1.2.3"}',
        encoding='utf-8',
    )

    metadata = RELEASE.refresh_release_metadata(release_json)

    assert metadata['board'] == 'RPI_PICO2_W'
    assert metadata['artifact_version'] == 'v1.2.3'
    assert metadata['firmware'] == firmware.name
    assert metadata['firmware_sha256'] == RELEASE.sha256_file(firmware)
    assert metadata['assets'] == [
        {
            'kind': 'firmware',
            'name': firmware.name,
            'sha256': RELEASE.sha256_file(firmware),
            'size_bytes': len(b'firmware'),
        },
        {
            'kind': 'bundle',
            'name': windows_zip.name,
            'sha256': RELEASE.sha256_file(windows_zip),
            'size_bytes': len(b'windows-zip'),
        },
    ]


def test_build_firmware_enables_usb_msc_and_records_metadata(tmp_path, monkeypatch) -> None:
    micropython = tmp_path / 'micropython'
    firmware = micropython / 'ports' / 'rp2' / 'build-RPI_PICO2_W' / 'firmware.uf2'
    firmware.parent.mkdir(parents=True)
    firmware.write_bytes(b'uf2')
    mpy_dir = tmp_path / 'mpy'
    mpy_dir.mkdir()
    (mpy_dir / 'boot.mpy').write_bytes(b'mpy')
    dist_dir = tmp_path / 'dist'
    release_json = dist_dir / 'release.json'
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path | None = None) -> None:
        assert cwd == micropython
        calls.append(cmd)

    monkeypatch.setattr(RELEASE, 'MICROPYTHON_DIR', micropython)
    monkeypatch.setattr(RELEASE, 'DIST_DIR', dist_dir)
    monkeypatch.setattr(RELEASE, 'RELEASE_JSON', release_json)
    monkeypatch.setattr(RELEASE, 'MPY_DIR', mpy_dir)
    monkeypatch.setattr(RELEASE, 'MANIFEST', tmp_path / 'manifest.py')
    monkeypatch.setattr(RELEASE, '_run', fake_run)

    output = RELEASE.build_firmware('RPI_PICO2_W', 'v1.28.0', {}, 'v0.0.1')

    assert output == dist_dir / 'pico-bit-RPI_PICO2_W-v0.0.1.uf2'
    assert output.read_bytes() == b'uf2'
    assert calls
    metadata = json.loads(release_json.read_text(encoding='utf-8'))
    assert metadata['usb_msc_enabled'] is True
    assert metadata['firmware'] == output.name
    assert metadata['usb_profile'] == 'default'


def test_resolve_usb_profile_returns_default_for_none_or_blank() -> None:
    assert RELEASE.resolve_usb_profile(None) is RELEASE.USB_IDENTITY_PROFILES['default']
    assert RELEASE.resolve_usb_profile('') is RELEASE.USB_IDENTITY_PROFILES['default']


def test_resolve_usb_profile_is_case_insensitive() -> None:
    assert (
        RELEASE.resolve_usb_profile('Generic-Composite')
        is RELEASE.USB_IDENTITY_PROFILES['generic-composite']
    )


def test_resolve_usb_profile_rejects_unknown_name() -> None:
    import pytest

    with pytest.raises(ValueError, match='unknown USB profile'):
        RELEASE.resolve_usb_profile('logitech-impersonator')


def test_write_usb_config_header_default_profile_keeps_pico_bit_branding(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(RELEASE, 'ROOT', tmp_path)
    header = RELEASE.write_usb_config_header()
    content = header.read_text(encoding='utf-8')
    assert '#define MICROPY_HW_USB_MANUFACTURER_STRING "Pico Bit"' in content
    assert '#define MICROPY_HW_USB_PRODUCT_FS_STRING "Pico Bit"' in content
    assert '#define MICROPY_HW_FLASH_FS_LABEL "PICO-BIT"' in content
    # Default profile must NOT override VID/PID — keeps the chip's real
    # Raspberry Pi VID to avoid Windows driver re-install on first plug.
    assert 'MICROPY_HW_USB_VID' not in content
    assert 'MICROPY_HW_USB_PID' not in content


def test_write_usb_config_header_generic_composite_strips_branding(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(RELEASE, 'ROOT', tmp_path)
    header = RELEASE.write_usb_config_header('generic-composite')
    content = header.read_text(encoding='utf-8')
    assert '"Pico Bit"' not in content
    assert '"PICOBIT"' not in content
    assert '#define MICROPY_HW_USB_MANUFACTURER_STRING "USB"' in content
    assert '#define MICROPY_HW_USB_PRODUCT_FS_STRING "USB Composite Device"' in content
    assert '#define MICROPY_HW_FLASH_FS_LABEL "USB-DRIVE"' in content
    assert 'MICROPY_HW_USB_VID' not in content


def test_write_usb_config_header_hobbyist_emits_vid_pid_overrides(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(RELEASE, 'ROOT', tmp_path)
    header = RELEASE.write_usb_config_header('hobbyist')
    content = header.read_text(encoding='utf-8')
    # V-USB shared range: 0x16C0 / 0x05DC.
    assert '#define MICROPY_HW_USB_VID (0x16c0)' in content
    assert '#define MICROPY_HW_USB_PID (0x05dc)' in content


def test_build_firmware_records_chosen_usb_profile_in_metadata(
    tmp_path,
    monkeypatch,
) -> None:
    micropython = tmp_path / 'micropython'
    firmware = micropython / 'ports' / 'rp2' / 'build-RPI_PICO2_W' / 'firmware.uf2'
    firmware.parent.mkdir(parents=True)
    firmware.write_bytes(b'uf2')
    mpy_dir = tmp_path / 'mpy'
    mpy_dir.mkdir()
    (mpy_dir / 'boot.mpy').write_bytes(b'mpy')
    dist_dir = tmp_path / 'dist'
    release_json = dist_dir / 'release.json'

    monkeypatch.setattr(RELEASE, 'ROOT', tmp_path)
    monkeypatch.setattr(RELEASE, 'MICROPYTHON_DIR', micropython)
    monkeypatch.setattr(RELEASE, 'DIST_DIR', dist_dir)
    monkeypatch.setattr(RELEASE, 'RELEASE_JSON', release_json)
    monkeypatch.setattr(RELEASE, 'MPY_DIR', mpy_dir)
    monkeypatch.setattr(RELEASE, 'MANIFEST', tmp_path / 'manifest.py')
    monkeypatch.setattr(RELEASE, '_run', lambda *a, **k: None)

    RELEASE.build_firmware(
        'RPI_PICO2_W',
        'v1.28.0',
        {},
        'v0.0.1',
        usb_profile='hobbyist',
    )
    metadata = json.loads(release_json.read_text(encoding='utf-8'))
    assert metadata['usb_profile'] == 'hobbyist'


def test_cli_accepts_usb_profile_flag() -> None:
    parser = RELEASE._build_parser()
    args = parser.parse_args(['build-uf2', '--usb-profile', 'generic-keyboard'])
    assert args.usb_profile == 'generic-keyboard'


def test_cli_rejects_unknown_usb_profile() -> None:
    import pytest

    parser = RELEASE._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['build-uf2', '--usb-profile', 'logitech'])


def test_cli_defaults_usb_profile_to_default() -> None:
    parser = RELEASE._build_parser()
    args = parser.parse_args(['build-uf2'])
    assert args.usb_profile == 'default'


def test_render_device_config_keeps_portal_password_independent() -> None:
    source = (ROOT / 'src' / 'device_config.py').read_text(encoding='utf-8')

    rendered = BUILD_PIPELINE.render_device_config(source, {'AP_PASSWORD': 'keyboard42'})

    assert "AP_PASSWORD: str = 'keyboard42'" in rendered
    assert "PORTAL_PASSWORD: str = 'PicoBit24Admin'" in rendered


def test_render_device_config_can_override_portal_login_values() -> None:
    source = (ROOT / 'src' / 'device_config.py').read_text(encoding='utf-8')

    rendered = BUILD_PIPELINE.render_device_config(
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


def test_build_module_overrides_uses_repo_payload_seed(tmp_path) -> None:
    (tmp_path / 'payload.dd').write_text('STRING seeded from file\n', encoding='utf-8')

    overrides = BUILD_PIPELINE.build_module_overrides(
        tmp_path,
        device_config_overrides={'AP_SSID': 'Studio Pico'},
    )

    assert overrides == {
        'device_config': {'AP_SSID': 'Studio Pico'},
        'ducky.constants': {'DEFAULT_PAYLOAD': 'STRING seeded from file\n'},
    }


def test_prepare_source_tree_applies_module_overrides(tmp_path, monkeypatch) -> None:
    src_dir = tmp_path / 'repo-src'
    ducky_dir = src_dir / 'ducky'
    ducky_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / 'device_config.py').write_text("AP_SSID: str = 'PicoBit'\n", encoding='utf-8')
    (ducky_dir / 'constants.py').write_text(
        "DEFAULT_PAYLOAD = 'REM default\\n'\n",
        encoding='utf-8',
    )
    monkeypatch.setattr(BUILD_PIPELINE, 'sync_web_assets', lambda: None)

    configured = BUILD_PIPELINE.prepare_source_tree(
        build_dir=tmp_path / 'build',
        root_src_dir=src_dir,
        overrides_by_module={
            'device_config': {'AP_SSID': 'Studio Pico'},
            'ducky.constants': {'DEFAULT_PAYLOAD': 'STRING seeded\n'},
        },
        minify_python=False,
    )

    assert "AP_SSID: str = 'Studio Pico'" in (configured / 'device_config.py').read_text(
        encoding='utf-8'
    )
    assert "DEFAULT_PAYLOAD = 'STRING seeded\\n'" in (
        configured / 'ducky' / 'constants.py'
    ).read_text(encoding='utf-8')


def test_prepare_source_tree_minifies_staged_python_sources(tmp_path, monkeypatch) -> None:
    src_dir = tmp_path / 'repo-src'
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / 'sample.py').write_text(
        """
def greet(name: str) -> str:
    note = "hello " + name
    return note
""".lstrip(),
        encoding='utf-8',
    )
    monkeypatch.setattr(BUILD_PIPELINE, 'sync_web_assets', lambda: None)

    plain = BUILD_PIPELINE.prepare_source_tree(
        build_dir=tmp_path / 'plain-build',
        root_src_dir=src_dir,
        minify_python=False,
    )
    minified = BUILD_PIPELINE.prepare_source_tree(
        build_dir=tmp_path / 'min-build',
        root_src_dir=src_dir,
        minify_python=True,
    )

    plain_source = (plain / 'sample.py').read_text(encoding='utf-8')
    minified_source = (minified / 'sample.py').read_text(encoding='utf-8')

    assert 'name: str' in plain_source
    assert '-> str' in plain_source
    assert 'name: str' not in minified_source
    assert '-> str' not in minified_source
    assert len(minified_source) < len(plain_source)


def test_build_mpy_tree_embeds_relative_source_names(tmp_path, monkeypatch) -> None:
    source_dir = tmp_path / 'src'
    output_dir = tmp_path / 'mpy'
    compiler_calls: list[list[str]] = []

    boot = source_dir / 'boot.py'
    srv = source_dir / 'server.py'
    parser = source_dir / 'ducky' / 'parser.py'
    srv.parent.mkdir(parents=True, exist_ok=True)
    parser.parent.mkdir(parents=True, exist_ok=True)
    boot.write_text('import main\n', encoding='utf-8')
    srv.write_text('VALUE = 1\n', encoding='utf-8')
    parser.write_text('VALUE = 2\n', encoding='utf-8')

    def fake_run(cmd: list[str], *, cwd: Path, check: bool) -> None:
        assert check is True
        assert cwd == ROOT
        compiler_calls.append(cmd)
        output = Path(cmd[cmd.index('-o') + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'mpy')

    monkeypatch.setattr(BUILD_PIPELINE.subprocess, 'run', fake_run)

    compiled = BUILD_PIPELINE.build_mpy_tree(
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
