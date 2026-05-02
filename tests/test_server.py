from __future__ import annotations

import asyncio
import json
import sys
import types
from typing import Any, cast

import pytest

import server


class FakeWriter:
    def __init__(self) -> None:
        self.buffer = b''
        self.closed = False

    def write(self, data: bytes) -> None:
        self.buffer += data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None

    def text(self) -> str:
        return self.buffer.decode('utf-8', 'ignore')


def _make_request(
    method: str,
    path: str,
    *,
    body: bytes = b'',
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
):
    return {
        'method': method,
        'path': path,
        'target': path,
        'headers': headers or {},
        'body': body,
        'cookies': cookies or {},
    }


def test_singleton_is_exported() -> None:
    assert isinstance(server.SERVER, server.SetupServer)


def test_login_page_renders_form() -> None:
    portal = server.SetupServer()

    html = portal._render_login('Nope', username='ana')

    assert 'Unlock injector' in html
    assert server.AP_SSID in html
    assert 'Invalid injector credentials.' not in html
    assert 'Nope' in html
    assert 'value="ana"' in html


def test_bootstrap_state_reports_payload_and_auth(monkeypatch) -> None:
    portal = server.SetupServer()
    portal._payload_seeded = True
    portal._ap_password_in_use = ''
    monkeypatch.setattr(portal, '_read_payload', lambda: 'REM test\n')
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')

    state = portal._bootstrap_state()

    assert state['payload'] == 'REM test\n'
    assert state['seeded'] is True
    assert state['auth_enabled'] is True
    assert state['ap_password'] == 'Open network'
    assert state['allow_unsafe'] is False
    assert state['message'] == 'payload.dd was seeded on this boot.'
    assert state['safe_mode_enabled'] is True


def test_bootstrap_state_reports_unsafe_runtime_when_enabled(monkeypatch) -> None:
    portal = server.SetupServer()
    portal._allow_unsafe = True
    monkeypatch.setattr(portal, '_read_payload', lambda: 'REM test\n')

    state = portal._bootstrap_state()

    assert state['allow_unsafe'] is True
    assert state['mode_label'] == 'Unsafe mode allowed'
    assert state['mode_short'] == 'Unsafe runtime enabled'
    assert state['safe_mode_enabled'] is False


def test_start_is_idempotent(monkeypatch) -> None:
    events: list[object] = []
    portal = server.SetupServer()

    class FakeServer:
        def close(self) -> None:
            events.append('close')

        async def wait_closed(self) -> None:
            events.append('wait_closed')

    async def fake_show(stage: str) -> None:
        events.append(('led', stage))

    async def fake_start_ap() -> str:
        events.append('ap')
        return '192.168.4.1'

    async def fake_start_server(_handler, host: str, port: int, backlog: int):
        events.append(('listen', host, port, backlog))
        return FakeServer()

    monkeypatch.setattr(portal, '_seed_payload', lambda: events.append('seed') or 'payload.dd')
    monkeypatch.setattr(portal, '_start_ap', fake_start_ap)
    monkeypatch.setattr(server.asyncio, 'start_server', fake_start_server)
    monkeypatch.setattr(server.STATUS_LED, 'show', fake_show)
    monkeypatch.setattr(server.STATUS_LED, 'on', lambda: events.append('on'))

    async def run() -> None:
        await portal.start()
        await portal.start()

    asyncio.run(run())

    assert events == [
        'seed',
        ('led', 'setup_ap_starting'),
        'ap',
        ('led', 'setup_ap_ready'),
        ('listen', '0.0.0.0', server.PORT, 3),
        ('led', 'setup_server_ready'),
        'on',
    ]


def _make_fake_network(fake_wlan_cls):
    return types.SimpleNamespace(WLAN=fake_wlan_cls, AP_IF=3)


def test_start_ap_configures_essid_and_password_before_activate(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    portal = server.SetupServer()

    class FakeWLAN:
        IF_AP = 3

        def __init__(self, interface: int) -> None:
            events.append(('init', interface))
            self._active = False

        def config(self, **kwargs) -> None:
            events.append(('config', kwargs))

        def active(self, value: bool | None = None) -> bool:
            if value is not None:
                events.append(('active', value))
                self._active = value
            return self._active

        def ifconfig(self) -> tuple[str, str, str, str]:
            return ('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8')

    monkeypatch.setattr(server, 'network', _make_fake_network(FakeWLAN))
    monkeypatch.setattr(server, 'sleep_ms', lambda _ms: asyncio.sleep(0))

    ip = asyncio.run(portal._start_ap())

    assert ip == '192.168.4.1'
    assert portal._ap is not None
    config_index = next(i for i, ev in enumerate(events) if ev[0] == 'config')
    activate_index = next(i for i, ev in enumerate(events) if ev == ('active', True))
    assert config_index < activate_index
    assert events[config_index][1] == {
        'essid': server.AP_SSID,
        'password': server.AP_PASSWORD,
    }


def test_start_ap_omits_password_when_blank(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    portal = server.SetupServer()

    class FakeWLAN:
        IF_AP = 3

        def __init__(self, _interface: int) -> None:
            self._active = False

        def config(self, **kwargs) -> None:
            events.append(('config', kwargs))

        def active(self, value: bool | None = None) -> bool:
            if value is not None:
                self._active = value
            return self._active

        def ifconfig(self) -> tuple[str, str, str, str]:
            return ('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8')

    monkeypatch.setattr(server, 'network', _make_fake_network(FakeWLAN))
    monkeypatch.setattr(server, 'AP_PASSWORD', '   ')
    monkeypatch.setattr(server, 'sleep_ms', lambda _ms: asyncio.sleep(0))

    ip = asyncio.run(portal._start_ap())

    assert ip == '192.168.4.1'
    assert portal._ap_password_in_use == ''
    assert ('config', {'essid': server.AP_SSID}) in events


def test_start_ap_raises_when_interface_never_activates(monkeypatch) -> None:
    portal = server.SetupServer()

    class FakeWLAN:
        IF_AP = 3

        def __init__(self, _interface: int) -> None:
            self._active = False

        def config(self, **_kwargs) -> None:
            return None

        def active(self, value: bool | None = None) -> bool:
            return False

        def ifconfig(self) -> tuple[str, str, str, str]:
            return ('0.0.0.0', '', '', '')

    monkeypatch.setattr(server, 'network', _make_fake_network(FakeWLAN))
    monkeypatch.setattr(server, 'sleep_ms', lambda _ms: asyncio.sleep(0))

    with pytest.raises(OSError, match='AP failed to come active'):
        asyncio.run(portal._start_ap())


def test_ensure_keyboard_is_lazy(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []
    portal = server.SetupServer()

    class FakeKeyboard:
        def is_open(self) -> bool:
            return True

        async def wait_open(self, timeout_ms: int) -> bool:
            calls.append(('wait_open', timeout_ms))
            return True

    fake_hid = types.SimpleNamespace(HIDKeyboard=FakeKeyboard)
    monkeypatch.setitem(sys.modules, 'hid', fake_hid)
    portal._kbd = None

    keyboard = asyncio.run(portal._ensure_keyboard())

    assert isinstance(keyboard, FakeKeyboard)
    assert calls == [('wait_open', server._USB_ENUM_TIMEOUT_MS)]


def test_execute_script_serializes_hid_use(monkeypatch) -> None:
    events: list[object] = []
    portal = server.SetupServer()
    fake_keyboard = object()

    class FakeLock:
        async def __aenter__(self):
            events.append('acquire')
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            events.append('release')
            return False

    async def fake_ensure_keyboard():
        return fake_keyboard

    async def fake_run_script(keyboard, script, allow_unsafe=False):
        events.append(('run', keyboard, script, allow_unsafe))

    monkeypatch.setattr(portal, '_run_lock_obj', lambda: FakeLock())
    monkeypatch.setattr(portal, '_ensure_keyboard', fake_ensure_keyboard)
    monkeypatch.setattr(
        server,
        'validate_script',
        lambda script: events.append(('validate', script)),
    )
    monkeypatch.setattr(server, 'run_script', fake_run_script)

    asyncio.run(portal.execute_script('STRING hi\n', allow_unsafe=True))

    assert events == [
        'acquire',
        ('validate', 'STRING hi\n'),
        ('run', fake_keyboard, 'STRING hi\n', True),
        'release',
    ]


def test_execute_script_uses_runtime_safe_mode_by_default(monkeypatch) -> None:
    events: list[object] = []
    portal = server.SetupServer()
    portal._allow_unsafe = True

    class FakeLock:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            return False

    async def fake_ensure_keyboard():
        return object()

    async def fake_run_script(_keyboard, script, allow_unsafe=False):
        events.append((script, allow_unsafe))

    monkeypatch.setattr(portal, '_run_lock_obj', lambda: FakeLock())
    monkeypatch.setattr(portal, '_ensure_keyboard', fake_ensure_keyboard)
    monkeypatch.setattr(server, 'validate_script', lambda _script: None)
    monkeypatch.setattr(server, 'run_script', fake_run_script)

    asyncio.run(portal.execute_script('STRING hi\n'))

    assert events == [('STRING hi\n', True)]


def test_dispatch_redirects_to_login_when_not_authorized(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')

    asyncio.run(portal._dispatch(_make_request('GET', '/'), writer))

    assert '303 See Other' in writer.text()
    assert 'Location: /login' in writer.text()


def test_dispatch_serves_assets_without_auth() -> None:
    portal = server.SetupServer()
    writer = FakeWriter()

    asyncio.run(portal._dispatch(_make_request('GET', '/assets/portal.js'), writer))

    response = writer.text()
    assert '200 OK' in response
    assert 'application/javascript' in response
    assert 'loadBootstrap' in response


def test_login_success_sets_cookie(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_USERNAME', 'admin')
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    monkeypatch.setattr(portal, '_new_session', lambda: 'token123')

    request = _make_request(
        'POST',
        '/login',
        body=b'username=admin&password=secret',
    )

    asyncio.run(portal._handle_login(request, writer))

    assert '303 See Other' in writer.text()
    assert 'Set-Cookie: pico_bit_session=token123;' in writer.text()


def test_api_bootstrap_returns_json_when_authorized(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(portal, '_bootstrap_state', lambda: {'payload': 'REM hi\n'})

    request = _make_request(
        'GET',
        '/api/bootstrap',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    assert '200 OK' in head
    assert 'application/json' in head
    assert json.loads(body)['payload'] == 'REM hi\n'


def test_api_safe_mode_updates_runtime_state(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(portal, '_read_payload', lambda: 'REM hi\n')

    request = _make_request(
        'POST',
        '/api/safe-mode',
        body=b'{"enabled": false}',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    payload = json.loads(body)
    assert '200 OK' in head
    assert portal._allow_unsafe is True
    assert payload['allow_unsafe'] is True
    assert payload['message'] == 'Safe mode disabled.'
    assert payload['mode_short'] == 'Unsafe runtime enabled'
    assert payload['safe_mode_enabled'] is False


def test_api_safe_mode_requires_boolean_flag() -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    request = _make_request(
        'POST',
        '/api/safe-mode',
        body=b'{"enabled": "nope"}',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    payload = json.loads(body)
    assert '400 Bad Request' in head
    assert payload == {
        'message': 'safe mode enabled must be a boolean.',
        'notice': 'error',
    }


def test_stop_closes_server_and_ap() -> None:
    events: list[str] = []
    portal = server.SetupServer()

    class FakeServer:
        def close(self) -> None:
            events.append('close')

        async def wait_closed(self) -> None:
            events.append('wait_closed')

    class FakeAP:
        def active(self, value: bool | None = None) -> bool:
            if value is False:
                events.append('ap_off')
            return False

    portal._server = cast(Any, FakeServer())
    portal._ap = cast(Any, FakeAP())

    asyncio.run(portal.stop())

    assert events == ['close', 'wait_closed', 'ap_off']
    assert portal._server is None
    assert portal._ap is None
