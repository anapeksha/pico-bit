import asyncio
import json

import server.routes_binary as routes_binary
import server.routes_loot as routes_loot
import server.routes_payload as routes_payload
from server import SetupServer


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
