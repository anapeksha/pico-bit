import asyncio
import json

import server.routes_binary as routes_binary
import server.routes_loot as routes_loot
import server.routes_payload as routes_payload
import server.routes_usb_agent as routes_usb_agent
from server import SetupServer
from usb_agent_drive import UsbAgentDrive


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
    static_dir = tmp_path / 'static'
    payload_bin = static_dir / 'payload.bin'
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    monkeypatch.setattr(routes_binary, '_STATIC_DIR', str(static_dir))
    monkeypatch.setattr(routes_binary, '_PAYLOAD_BIN', str(payload_bin))

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


def test_handle_binary_upload_stream_accepts_extensionless_elf_binary(
    tmp_path, monkeypatch
) -> None:
    static_dir = tmp_path / 'static'
    payload_bin = static_dir / 'payload.bin'
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    monkeypatch.setattr(routes_binary, '_STATIC_DIR', str(static_dir))
    monkeypatch.setattr(routes_binary, '_PAYLOAD_BIN', str(payload_bin))

    body = b'\x7fELF\x02\x01\x01\x00hello'
    reader = FakeReader(body)
    writer = FakeWriter()
    request = _request('/api/upload_binary', headers={'x-filename': 'agent'})

    asyncio.run(server._handle_binary_upload_stream(reader, writer, request, len(body)))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 200 OK'
    assert payload['notice'] == 'success'
    assert payload['filename'] == 'agent'
    assert payload['size'] == len(body)
    assert payload_bin.read_bytes() == body


def test_handle_loot_receive_persists_timestamp_and_publishes(tmp_path, monkeypatch) -> None:
    loot_file = tmp_path / 'loot.json'
    server = SetupServer()
    monkeypatch.setattr(routes_loot, '_LOOT_FILE', str(loot_file))

    writer = FakeWriter()
    request = _request('/api/loot', body={'system': {'hostname': 'test-host'}})

    asyncio.run(server._handle_loot_receive(request, writer))
    status, payload = _json_response(writer)

    saved = json.loads(loot_file.read_text(encoding='utf-8'))
    revision, published = server._loot_stream.snapshot()

    assert status == 'HTTP/1.1 200 OK'
    assert payload['message'] == 'Loot saved.'
    assert isinstance(payload['timestamp'], int)
    assert saved['system']['hostname'] == 'test-host'
    assert saved['timestamp'] == payload['timestamp']
    assert revision == 1
    assert json.loads(published)['timestamp'] == payload['timestamp']


def test_handle_loot_get_returns_saved_record(tmp_path, monkeypatch) -> None:
    loot_file = tmp_path / 'loot.json'
    loot_file.write_text(
        json.dumps({'system': {'hostname': 'pico'}, 'timestamp': 123}),
        encoding='utf-8',
    )
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
    saved = json.loads(loot_file.read_text(encoding='utf-8'))
    revision, published = server._loot_stream.snapshot()

    assert status == 'HTTP/1.1 200 OK'
    assert payload['notice'] == 'success'
    assert saved['system']['hostname'] == 'usb-host'
    assert saved['source'] == 'usb_drive'
    assert revision == 1
    assert json.loads(published)['source'] == 'usb_drive'
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


class FakeUsbAgentDrive(UsbAgentDrive):
    def __init__(self) -> None:
        self.mounted = False

    def state(self) -> dict[str, object]:
        return {
            'available': True,
            'can_mount': not self.mounted,
            'filename': 'pico-agent',
            'mounted': self.mounted,
            'state': 'mounted' if self.mounted else 'inactive',
            'volume_label': 'PICOBIT',
            'message': (
                'USB agent drive is armed.' if self.mounted else 'USB agent drive is inactive.'
            ),
        }

    def set_mounted(self, mounted: bool, *, agent_path: str) -> dict[str, object]:
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
    fake_drive = FakeUsbAgentDrive()
    server._usb_agent_drive = fake_drive

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


def test_inject_binary_uses_usb_drive_delivery(monkeypatch) -> None:
    shown: list[str] = []
    captured: dict[str, object] = {}
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    fake_drive = FakeUsbAgentDrive()
    fake_drive.mounted = True
    server._usb_agent_drive = fake_drive

    async def fake_show(stage: str) -> None:
        shown.append(stage)

    async def fake_run_payload(script: str, *, source: str = 'portal') -> tuple[str, str]:
        captured['script'] = script
        captured['source'] = source
        return 'Payload executed.', 'success'

    monkeypatch.setattr(routes_payload.STATUS_LED, 'show', fake_show)
    server._run_payload = fake_run_payload  # type: ignore[method-assign]

    writer = FakeWriter()
    request = _request('/api/inject_binary', body={'os': 'linux', 'delivery': 'usb_drive'})

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 200 OK'
    assert payload['notice'] == 'success'
    assert captured['source'] == 'binary:usb_drive'
    assert 'PICOBIT' in str(captured['script'])
    assert shown == ['binary_injecting']


def test_usb_drive_windows_stager_copies_extensionless_agent_to_exe() -> None:
    server = SetupServer()
    server._ap_ip = '192.168.4.1'

    script = server._stager_script('windows', delivery='usb_drive')

    assert ':/pico-agent' in script
    assert '--loot-out' in script
    assert 'loot-usb.json' in script
    assert 'pico_agent.exe' in script
    assert 'pico-agent.exe' not in script
    assert 'Remove-Item' in script


def test_usb_drive_linux_stager_writes_usb_loot_and_removes_temp_agent() -> None:
    server = SetupServer()
    server._ap_ip = '192.168.4.1'

    script = server._stager_script('linux', delivery='usb_drive')

    assert '--loot-out "$d/loot-usb.json"' in script
    assert 'rm -f /tmp/pico_agent' in script


def test_network_stager_runs_ephemerally() -> None:
    server = SetupServer()
    server._ap_ip = '192.168.4.1'

    windows = server._stager_script('windows', delivery='network')
    linux = server._stager_script('linux', delivery='network')

    assert 'Remove-Item $p' in windows
    assert 'rm -f /tmp/pico_agent' in linux


def test_inject_binary_rejects_usb_delivery_when_unmounted() -> None:
    server = SetupServer()
    server._is_authorized = lambda request: True  # type: ignore[method-assign]
    server._has_binary = lambda: True  # type: ignore[method-assign]
    fake_drive = FakeUsbAgentDrive()
    server._usb_agent_drive = fake_drive

    writer = FakeWriter()
    request = _request('/api/inject_binary', body={'os': 'linux', 'delivery': 'usb_drive'})

    asyncio.run(server._handle_api(request, writer))
    status, payload = _json_response(writer)

    assert status == 'HTTP/1.1 400 Bad Request'
    assert payload['notice'] == 'error'
    assert 'Mount the USB agent drive' in str(payload['message'])
