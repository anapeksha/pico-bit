import asyncio
import json

import server.api.binary as routes_binary
import server.api.loot as routes_loot
import server.api.payload as routes_payload
import server.api.usb_agent as routes_usb_agent
from server import SetupServer
from usb import USBService


class FakeReader:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.bytes_read = 0

    async def read(self, size: int) -> bytes:
        chunk = self._body[:size]
        self._body = self._body[size:]
        self.bytes_read += len(chunk)
        return chunk


class FakeWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None


def _request(
    path: str,
    *,
    method: str = 'POST',
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    payload = b''
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode('utf-8')
        request_headers.setdefault('content-type', 'application/json')
    return {
        'method': method,
        'path': path,
        'headers': request_headers,
        'cookies': {},
        'body': payload,
    }


def _json_response(writer: FakeWriter) -> tuple[str, dict[str, object]]:
    raw = bytes(writer.buffer)
    head, body = raw.split(b'\r\n\r\n', 1)
    status = head.decode('utf-8').splitlines()[0]
    return status, json.loads(body.decode('utf-8'))


def _raw_response(writer: FakeWriter) -> tuple[str, str]:
    raw = bytes(writer.buffer)
    head, body = raw.split(b'\r\n\r\n', 1)
    status = head.decode('utf-8').splitlines()[0]
    return status, body.decode('utf-8')


def test_render_app_switches_single_spa_between_login_and_portal() -> None:
    server = SetupServer()

    login = server._render_login('Invalid <user>', '<admin>')
    portal = server._render_portal()

    assert 'data-auth-state="login"' in login
    assert 'id="app"' in login
    assert 'data-message="Invalid &lt;user&gt;"' in login
    assert 'data-username="&lt;admin&gt;"' in login
    assert 'data-auth-state="portal"' in portal
    assert '{{auth_state}}' not in portal


def test_root_serves_login_state_for_unauthorized_spa_request() -> None:
    server = SetupServer()
    server._is_authorized = lambda request: False  # type: ignore[method-assign]
    writer = FakeWriter()
    request = _request('/', method='GET')

    asyncio.run(server._dispatch(request, writer))
    status, body = _raw_response(writer)

    assert status == 'HTTP/1.1 200 OK'
    assert 'data-auth-state="login"' in body
    assert 'id="app"' in body


def test_static_index_assets_are_served_by_index_names() -> None:
    server = SetupServer()
    for path, content_type in (
        ('/assets/index.css', 'text/css; charset=utf-8'),
        ('/assets/index.js', 'application/javascript; charset=utf-8'),
    ):
        writer = FakeWriter()
        request = _request(path, method='GET')

        asyncio.run(server._dispatch(request, writer))
        raw = bytes(writer.buffer)
        head, body = raw.split(b'\r\n\r\n', 1)

        assert head.decode('utf-8').splitlines()[0] == 'HTTP/1.1 200 OK'
        assert f'Content-Type: {content_type}' in head.decode('utf-8')
        assert body


def test_bootstrap_state_exposes_keyboard_target_metadata() -> None:
    server = SetupServer()
    server._ap_ip = '192.168.4.1'
    server._ap_password_in_use = 'PicoBit24Net'
    server._read_payload = lambda: 'STRING hi\n'  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    server._keyboard_ready = lambda: True  # type: ignore[method-assign]

    state = server._bootstrap_state()

    assert state['payload'] == 'STRING hi\n'
    assert state['has_binary'] is True
    assert state['keyboard_os'] == 'WIN'
    assert state['keyboard_layout'] == 'US'
    assert state['keyboard_target_label'] == 'Windows · English (US)'


def test_handle_api_updates_keyboard_layout_and_persists_choice(tmp_path, monkeypatch) -> None:
    saved_stages: list[str] = []
    layout_file = tmp_path / 'keyboard_layout.txt'
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    monkeypatch.setattr(routes_payload, '_KEYBOARD_LAYOUT_FILE', str(layout_file))

    async def fake_show(stage: str) -> None:
        saved_stages.append(stage)

    monkeypatch.setattr(routes_payload.STATUS_LED, 'show', fake_show)

    writer = FakeWriter()
    request = _request('/api/keyboard-layout', body={'os': 'mac', 'layout': 'fr'})

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 200 OK'
    assert payload['notice'] == 'success'
    assert payload['keyboard_os'] == 'MAC'
    assert payload['keyboard_layout'] == 'FR'
    assert payload['keyboard_target_label'] == 'macOS · French (FR)'
    assert layout_file.read_text(encoding='utf-8') == 'MAC_FR\n'
    assert saved_stages == ['keyboard_layout_changed']


def test_handle_api_rejects_unsupported_layout_for_platform(monkeypatch) -> None:
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]

    writer = FakeWriter()
    request = _request('/api/keyboard-layout', body={'os': 'mac', 'layout': 'de'})

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 400 Bad Request'
    assert payload['notice'] == 'error'
    assert payload['message'] == 'Unsupported keyboard layout for macOS.'
    assert server._keyboard_layout == 'WIN_US'


def test_handle_binary_upload_stream_rejects_non_binary_content(tmp_path, monkeypatch) -> None:
    payload_bin = tmp_path / 'payload.bin'
    payload_exe = tmp_path / 'payload.exe'
    upload_tmp = tmp_path / 'payload.upload'
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    monkeypatch.setattr(routes_binary, '_PAYLOAD_BIN', str(payload_bin))
    monkeypatch.setattr(routes_binary, '_PAYLOAD_EXE', str(payload_exe))
    monkeypatch.setattr(routes_binary, '_STAGED_UPLOAD_TEMP', str(upload_tmp))

    body = b'\x89PNG\r\n\x1a\nnot a binary payload'
    reader = FakeReader(body)
    writer = FakeWriter()
    request = _request('/api/upload_binary', headers={'x-filename': 'agent.bin'})

    asyncio.run(server._handle_binary_upload_stream(reader, writer, request, len(body)))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 400 Bad Request'
    assert payload['notice'] == 'error'
    assert payload['message'] == 'Only executable EXE, ELF, or Mach-O binaries can be uploaded.'
    assert reader.bytes_read == len(body)
    assert not payload_bin.exists()
    assert not payload_exe.exists()


def test_handle_binary_upload_stream_accepts_extensionless_elf_binary(
    tmp_path, monkeypatch
) -> None:
    payload_bin = tmp_path / 'payload.bin'
    payload_exe = tmp_path / 'payload.exe'
    upload_tmp = tmp_path / 'payload.upload'
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]

    class UploadUSBService(USBService):
        def __init__(self) -> None:
            self.mounted = False
            self.refreshed = False

        def state(self) -> dict[str, object]:
            return {
                'active': self.mounted,
                'available': True,
                'can_mount': not self.mounted,
                'can_unmount': self.mounted,
                'filename': 'payload.bin',
                'has_binary': self.mounted,
                'mounted': self.mounted,
                'state': 'active' if self.mounted else 'inactive',
                'message': 'USB injector is active.',
            }

        def set_mounted(self, mounted: bool, *, agent_path: str = '') -> dict[str, object]:
            del agent_path
            self.mounted = mounted
            return self.state()

        def refresh(self) -> bool:
            self.refreshed = True
            return True

    fake_usb = UploadUSBService()
    server._usb = fake_usb
    monkeypatch.setattr(routes_binary, '_PAYLOAD_BIN', str(payload_bin))
    monkeypatch.setattr(routes_binary, '_PAYLOAD_EXE', str(payload_exe))
    monkeypatch.setattr(routes_binary, '_STAGED_UPLOAD_TEMP', str(upload_tmp))

    body = b'\x7fELF\x02\x01\x01\x00hello'
    reader = FakeReader(body)
    writer = FakeWriter()
    request = _request('/api/upload_binary', headers={'x-filename': 'agent'})

    asyncio.run(server._handle_binary_upload_stream(reader, writer, request, len(body)))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 200 OK'
    assert payload['notice'] == 'success'
    assert payload['filename'] == 'payload.bin'
    assert payload['size'] == len(body)
    assert isinstance(payload['usb_agent'], dict)
    assert payload['usb_agent']['mounted'] is True
    assert fake_usb.refreshed is True
    assert payload_bin.read_bytes() == body
    assert not payload_exe.exists()


def test_handle_loot_receive_persists_timestamp_and_publishes(tmp_path, monkeypatch) -> None:
    loot_file = tmp_path / 'loot.json'
    server = SetupServer()
    monkeypatch.setattr(routes_loot, '_LOOT_FILE', str(loot_file))

    writer = FakeWriter()
    request = _request('/api/loot', body={'system': {'hostname': 'test-host'}})

    asyncio.run(server._handle_loot_receive(request, writer))
    status, payload = _json_response(writer)

    saved = json.loads(loot_file.read_text())

    assert status == 'HTTP/1.1 200 OK'
    assert payload['message'] == 'Loot saved.'
    assert isinstance(payload['timestamp'], int)
    assert saved['system']['hostname'] == 'test-host'
    assert saved['timestamp'] == payload['timestamp']


def test_handle_loot_get_returns_saved_record(tmp_path, monkeypatch) -> None:
    loot_file = tmp_path / 'loot.json'
    loot_file.write_text(json.dumps({'system': {'hostname': 'pico'}, 'timestamp': 123}))
    server = SetupServer()
    monkeypatch.setattr(routes_loot, '_LOOT_FILE', str(loot_file))

    writer = FakeWriter()
    request = _request('/api/loot', method='GET')

    asyncio.run(server._handle_loot_get(request, writer))
    status, payload = _json_response(writer)

    system = payload['system']

    assert status == 'HTTP/1.1 200 OK'
    assert isinstance(system, dict)
    assert system['hostname'] == 'pico'
    assert payload['timestamp'] == 123


def test_handle_loot_download_returns_json_attachment(tmp_path, monkeypatch) -> None:
    loot_file = tmp_path / 'loot.json'
    loot_file.write_text(json.dumps({'system': {'arch': 'aarch64'}, 'timestamp': 456}))
    server = SetupServer()
    monkeypatch.setattr(routes_loot, '_LOOT_FILE', str(loot_file))

    writer = FakeWriter()
    request = _request('/api/loot/download', method='GET')

    asyncio.run(server._handle_loot_download(request, writer))

    raw = bytes(writer.buffer)
    head, body = raw.split(b'\r\n\r\n', 1)
    header_text = head.decode('utf-8')
    payload = json.loads(body.decode('utf-8'))

    assert header_text.startswith('HTTP/1.1 200 OK')
    assert 'Content-Disposition: attachment; filename="loot.json"' in header_text
    assert payload['system']['arch'] == 'aarch64'


def test_handle_usb_loot_import_promotes_usb_file_to_canonical_loot(tmp_path, monkeypatch) -> None:
    shown: list[str] = []
    loot_file = tmp_path / 'loot.json'
    usb_loot_file = tmp_path / 'loot-usb.json'
    usb_loot_file.write_text(
        json.dumps({'system': {'hostname': 'usb-host'}, 'type': 'recon'}),
        encoding='utf-8',
    )
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    monkeypatch.setattr(routes_loot, '_LOOT_FILE', str(loot_file))
    monkeypatch.setattr(routes_loot, '_USB_LOOT_FILE', str(usb_loot_file))

    async def fake_show(stage: str) -> None:
        shown.append(stage)

    monkeypatch.setattr(routes_loot.STATUS_LED, 'show', fake_show)

    writer = FakeWriter()
    request = _request('/api/loot/import-usb')

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)
    saved = json.loads(loot_file.read_text())

    assert status == 'HTTP/1.1 200 OK'
    assert payload['notice'] == 'success'
    assert saved['system']['hostname'] == 'usb-host'
    assert saved['source'] == 'usb_drive'
    assert not usb_loot_file.exists()
    assert shown == ['loot_imported']


def test_handle_usb_loot_import_reports_missing_file(tmp_path, monkeypatch) -> None:
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    monkeypatch.setattr(routes_loot, '_USB_LOOT_FILE', str(tmp_path / 'missing.json'))

    writer = FakeWriter()
    request = _request('/api/loot/import-usb')

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 404 Not Found'
    assert payload['notice'] == 'error'
    assert payload['message'] == 'No USB loot file found.'


class FakeUSBService(USBService):
    def __init__(self) -> None:
        self.mounted = False

    def state(self) -> dict[str, object]:
        return {
            'active': self.mounted,
            'available': True,
            'can_mount': not self.mounted,
            'can_unmount': self.mounted,
            'filename': 'payload.bin',
            'has_binary': self.mounted,
            'mounted': self.mounted,
            'state': 'active' if self.mounted else 'inactive',
            'volume_label': '',
            'volume_note': 'Host volume names come from the filesystem and may appear as No Name.',
            'message': ('USB injector is active.' if self.mounted else 'USB injector is inactive.'),
        }

    def set_mounted(self, mounted: bool, *, agent_path: str = '') -> dict[str, object]:
        del agent_path
        self.mounted = mounted
        return self.state()


def test_usb_agent_route_requires_authentication() -> None:
    server = SetupServer()
    server._is_authorized = lambda request: False  # type: ignore[method-assign]

    writer = FakeWriter()
    request = _request('/api/usb-agent', method='GET')

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 401 Unauthorized'
    assert payload['message'] == 'Sign in required.'


def test_usb_agent_route_mounts_fake_drive(monkeypatch) -> None:
    shown: list[str] = []
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    fake_drive = FakeUSBService()
    server._usb = fake_drive

    async def fake_show(stage: str) -> None:
        shown.append(stage)

    monkeypatch.setattr(routes_usb_agent.STATUS_LED, 'show', fake_show)

    writer = FakeWriter()
    request = _request('/api/usb-agent', body={'mounted': True})

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)
    usb_agent = payload['usb_agent']

    assert status == 'HTTP/1.1 200 OK'
    assert isinstance(usb_agent, dict)
    assert usb_agent['mounted'] is True
    assert usb_agent['has_binary'] is True
    assert shown == ['usb_agent_mounted']


def test_inject_binary_uses_usb_drive_delivery(tmp_path, monkeypatch) -> None:
    shown: list[str] = []
    captured: dict[str, object] = {}
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    fake_drive = FakeUSBService()
    fake_drive.mounted = True
    server._usb = fake_drive
    monkeypatch.setattr(routes_loot, '_LOOT_FILE', str(tmp_path / 'loot.json'))

    async def fake_show(stage: str) -> None:
        shown.append(stage)

    async def fake_run_payload(script: str, *, source: str = 'portal') -> tuple[str, str]:
        captured['script'] = script
        captured['source'] = source
        return 'Payload executed.', 'success'

    monkeypatch.setattr(routes_payload.STATUS_LED, 'show', fake_show)
    server._run_payload = fake_run_payload  # type: ignore[method-assign]
    server._binary_matches_target = lambda target_os: True  # type: ignore[method-assign]

    writer = FakeWriter()
    request = _request('/api/inject_binary', body={'os': 'linux'})

    # Handler returns immediately; background task runs on sleep(0).
    async def run() -> None:
        await server._handle_api(request, writer)
        await asyncio.sleep(0)

    asyncio.run(run())
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 200 OK'
    assert payload['notice'] == 'success'
    assert payload['message'] == 'Injection started.'
    assert captured['source'] == 'binary:usb'
    assert 'payload.bin' in str(captured['script'])
    assert shown == ['binary_injecting']


def test_inject_binary_ignores_client_supplied_stager_command(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    fake_drive = FakeUSBService()
    fake_drive.mounted = True
    server._usb = fake_drive
    monkeypatch.setattr(routes_loot, '_LOOT_FILE', str(tmp_path / 'loot.json'))

    async def fake_run_payload(script: str, *, source: str = 'portal') -> tuple[str, str]:
        captured['script'] = script
        captured['source'] = source
        return 'Payload executed.', 'success'

    async def fake_show(_stage: str) -> None:
        return None

    monkeypatch.setattr(routes_payload.STATUS_LED, 'show', fake_show)
    server._run_payload = fake_run_payload  # type: ignore[method-assign]
    server._binary_matches_target = lambda target_os: True  # type: ignore[method-assign]

    writer = FakeWriter()
    request = _request(
        '/api/inject_binary',
        body={
            'os': 'macos',
            'command': 'echo client-controlled',
            'script': 'STRING echo client-controlled',
        },
    )

    async def run() -> None:
        await server._handle_api(request, writer)
        await asyncio.sleep(0)

    asyncio.run(run())
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 200 OK'
    assert payload['notice'] == 'success'
    assert payload['message'] == 'Injection started.'
    assert captured['source'] == 'binary:usb'
    assert 'client-controlled' not in str(captured['script'])
    assert '/Volumes/*' in str(captured['script'])
    assert '/tmp/pa' in str(captured['script'])
    assert '--loot-out' in str(captured['script'])


def test_inject_binary_rejects_unknown_target_os() -> None:
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    fake_drive = FakeUSBService()
    fake_drive.mounted = True
    server._usb = fake_drive

    writer = FakeWriter()
    request = _request('/api/inject_binary', body={'os': 'freebsd'})

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 400 Bad Request'
    assert payload['notice'] == 'error'
    assert payload['message'] == 'Unsupported binary injection target OS.'


def test_usb_drive_windows_stager_copies_extensionless_agent_to_exe() -> None:
    server = SetupServer()
    script = server._stager_script('windows')

    assert 'powershell -NoProfile -ExecutionPolicy Bypass' in script
    assert 'DEFAULTCHARDELAY 10' in script
    assert 'foreach($d in Get-PSDrive -PSProvider FileSystem)' in script
    assert 'payload.exe' in script
    assert '--loot-out' in script
    assert 'loot-usb.json' in script
    assert "Join-Path $env:TEMP 'pa.exe'" in script
    assert 'if($?)' in script
    assert 'del $x -ea 0' in script
    assert script.count('STRING ') == 2
    assert script.count('\nENTER\n') == 2


def test_usb_drive_linux_stager_writes_usb_loot_and_removes_temp_agent() -> None:
    server = SetupServer()
    script = server._stager_script('linux')

    assert 'CTRL-ALT t' in script
    assert 'DEFAULTCHARDELAY 30' in script
    assert '/media/$USER/* /run/media/$USER/* /mnt/*' in script
    assert 'payload.bin' in script
    assert '--loot-out "$d/loot-usb.json"' in script
    assert '/tmp/pa' in script
    assert 'rm -f /tmp/pa' in script
    assert script.count('STRING ') == 1
    assert script.count('\nENTER\n') == 1


def test_usb_drive_macos_stager_waits_for_terminal_and_types_multiline_script() -> None:
    server = SetupServer()
    script = server._stager_script('macos')

    assert 'GUI SPACE' in script
    assert 'STRING Terminal\nENTER' in script
    assert 'DELAY 6000' in script
    assert 'DEFAULTCHARDELAY 30' in script
    assert '/Volumes/*' in script
    assert 'payload.bin' in script
    assert '--loot-out "$d/loot-usb.json"' in script
    assert '/tmp/pa' in script
    assert 'rm -f /tmp/pa' in script
    assert script.count('STRING ') == 2
    assert script.count('\nENTER\n') == 2


def test_inject_binary_rejects_mismatched_binary_for_target() -> None:
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    fake_drive = FakeUSBService()
    fake_drive.mounted = True
    server._usb = fake_drive
    server._binary_matches_target = lambda target_os: target_os == 'linux'  # type: ignore[method-assign]

    writer = FakeWriter()
    request = _request('/api/inject_binary', body={'os': 'windows'})

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 400 Bad Request'
    assert payload['notice'] == 'error'
    assert 'Windows PE binary' in str(payload['message'])


def test_inject_binary_rejects_usb_delivery_when_unmounted() -> None:
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    fake_drive = FakeUSBService()
    server._usb = fake_drive

    writer = FakeWriter()
    request = _request('/api/inject_binary', body={'os': 'linux'})

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 400 Bad Request'
    assert payload['notice'] == 'error'
    assert 'Activate the USB injector' in str(payload['message'])
