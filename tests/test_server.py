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
    assert state['keyboard_layout_code'] == 'US'
    assert state['keyboard_layout_label'] == 'English (US)'
    assert state['keyboard_layout_profile_code'] == 'WIN_US'
    assert state['keyboard_os_code'] == 'WIN'
    assert state['keyboard_target_label'] == 'Windows · English (US)'
    assert state['message'] == 'payload.dd was seeded on this boot.'
    assert state['safe_mode_enabled'] is True


def test_bootstrap_state_reports_unsafe_runtime_when_enabled(monkeypatch) -> None:
    portal = server.SetupServer()
    portal._allow_unsafe = True
    monkeypatch.setattr(portal, '_read_payload', lambda: 'REM test\n')

    state = portal._bootstrap_state()

    assert state['allow_unsafe'] is True
    assert state['keyboard_layout'] == 'US'
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
    portal._keyboard_layout = 'WIN_DE'
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

    async def fake_run_script(keyboard, script, allow_unsafe=False, default_layout='WIN_US'):
        events.append(('run', keyboard, script, allow_unsafe, default_layout))

    monkeypatch.setattr(portal, '_run_lock_obj', lambda: FakeLock())
    monkeypatch.setattr(portal, '_ensure_keyboard', fake_ensure_keyboard)
    monkeypatch.setattr(
        server,
        'validate_script',
        lambda script: events.append(('validate', script)),
    )
    monkeypatch.setattr(server, 'run_script', fake_run_script)
    monkeypatch.setattr(
        server.STATUS_LED,
        'show',
        lambda stage: asyncio.sleep(0, result=events.append(('led', stage))),
    )

    asyncio.run(portal.execute_script('STRING hi\n', allow_unsafe=True))

    assert events == [
        'acquire',
        ('validate', 'STRING hi\n'),
        ('led', 'payload_running'),
        ('run', fake_keyboard, 'STRING hi\n', True, 'WIN_DE'),
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

    async def fake_run_script(_keyboard, script, allow_unsafe=False, default_layout='WIN_US'):
        events.append((script, allow_unsafe, default_layout))

    monkeypatch.setattr(portal, '_run_lock_obj', lambda: FakeLock())
    monkeypatch.setattr(portal, '_ensure_keyboard', fake_ensure_keyboard)
    monkeypatch.setattr(server, 'validate_script', lambda _script: None)
    monkeypatch.setattr(server, 'run_script', fake_run_script)
    monkeypatch.setattr(server.STATUS_LED, 'show', lambda _stage: asyncio.sleep(0))

    asyncio.run(portal.execute_script('STRING hi\n'))

    assert events == [('STRING hi\n', True, 'WIN_US')]


def test_run_payload_records_recent_history(monkeypatch) -> None:
    portal = server.SetupServer()

    async def fake_execute_script(script: str, allow_unsafe: bool | None = None) -> None:
        assert script == 'STRING hi\n'
        assert allow_unsafe is None

    monkeypatch.setattr(portal, 'execute_script', fake_execute_script)

    message, notice = asyncio.run(portal._run_payload('STRING hi\n'))

    assert (message, notice) == ('Payload executed.', 'success')
    assert portal._run_history[0]['source'] == 'portal'
    assert portal._run_history[0]['preview'] == 'STRING hi'


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
    events: list[str] = []
    monkeypatch.setattr(portal, '_read_payload', lambda: 'REM hi\n')
    monkeypatch.setattr(portal, '_validation_state', lambda _script: {'blocking': False})
    monkeypatch.setattr(
        server.STATUS_LED,
        'show',
        lambda stage: asyncio.sleep(0, result=events.append(stage)),
    )

    request = _make_request(
        'POST',
        '/api/safe-mode',
        body=b'{"enabled": false, "payload": "STRING hi\\n"}',
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
    assert payload['validation'] == {'blocking': False}
    assert events == ['safe_mode_changed']


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


def test_api_keyboard_layout_updates_runtime_state(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    events: list[str] = []
    persisted: list[str] = []
    monkeypatch.setattr(portal, '_persist_keyboard_layout', lambda code: persisted.append(code))
    monkeypatch.setattr(
        server.STATUS_LED,
        'show',
        lambda stage: asyncio.sleep(0, result=events.append(stage)),
    )
    request = _make_request(
        'POST',
        '/api/keyboard-layout',
        body=b'{"os": "WIN", "layout": "DE"}',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    payload = json.loads(body)
    assert '200 OK' in head
    assert portal._keyboard_layout == 'WIN_DE'
    assert payload['keyboard_layout_code'] == 'DE'
    assert payload['keyboard_layout_label'] == 'German (DE)'
    assert payload['keyboard_layout_profile_code'] == 'WIN_DE'
    assert payload['keyboard_os_code'] == 'WIN'
    assert payload['message'] == 'Typing target set to Windows · German (DE).'
    assert persisted == ['WIN_DE']
    assert events == ['keyboard_layout_changed']


def test_api_keyboard_layout_switches_os_and_uses_platform_default(monkeypatch) -> None:
    portal = server.SetupServer()
    portal._keyboard_layout = 'WIN_DE'
    writer = FakeWriter()
    persisted: list[str] = []
    monkeypatch.setattr(portal, '_persist_keyboard_layout', lambda code: persisted.append(code))
    monkeypatch.setattr(server.STATUS_LED, 'show', lambda _stage: asyncio.sleep(0))
    request = _make_request(
        'POST',
        '/api/keyboard-layout',
        body=b'{"os": "MAC"}',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    payload = json.loads(body)
    assert '200 OK' in head
    assert portal._keyboard_layout == 'MAC_US'
    assert payload['keyboard_os_code'] == 'MAC'
    assert payload['keyboard_layout_code'] == 'US'
    assert payload['keyboard_layouts'] == [
        {'code': 'US', 'label': 'English (US)'},
        {'code': 'FR', 'label': 'French (FR)'},
    ]
    assert payload['message'] == 'Typing target set to macOS · English (US).'
    assert persisted == ['MAC_US']


def test_api_keyboard_layout_rejects_unknown_value() -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    request = _make_request(
        'POST',
        '/api/keyboard-layout',
        body=b'{"os": "MAC", "layout": "DE"}',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    payload = json.loads(body)
    assert '400 Bad Request' in head
    assert payload['message'] == 'Unsupported keyboard layout for macOS.'


def test_api_validate_returns_dry_run_state(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(
        portal,
        '_validation_state',
        lambda script: {'blocking': False, 'summary': f'validated {script}', 'notice': 'success'},
    )
    request = _make_request(
        'POST',
        '/api/validate',
        body=b'{"payload": "STRING hi\\n"}',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    payload = json.loads(body)
    assert '200 OK' in head
    assert payload['message'] == 'validated STRING hi\n'
    assert payload['validation']['blocking'] is False


def test_api_payload_rejects_blocking_validation(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(
        portal,
        '_validation_state',
        lambda _script: {'blocking': True, 'summary': 'Fix 1 error.', 'notice': 'error'},
    )
    request = _make_request(
        'POST',
        '/api/payload',
        body=b'{"payload": "WAIT_FOR_CAPS_ON\\n"}',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    payload = json.loads(body)
    assert '400 Bad Request' in head
    assert payload['message'] == 'Fix 1 error.'
    assert payload['validation']['blocking'] is True


def test_api_run_returns_recent_history(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(
        portal,
        '_validation_state',
        lambda _script: {'blocking': False, 'summary': 'ready', 'notice': 'success'},
    )
    monkeypatch.setattr(portal, '_write_payload', lambda _payload: 'payload.dd')
    monkeypatch.setattr(
        portal,
        '_run_payload',
        lambda payload: asyncio.sleep(0, result=('Payload executed.', 'success')),
    )
    monkeypatch.setattr(
        portal,
        '_recent_runs',
        lambda: [{'sequence': 1, 'notice': 'success', 'preview': 'STRING hi'}],
    )

    request = _make_request(
        'POST',
        '/api/run',
        body=b'{"payload": "STRING hi\\n", "save": true}',
        cookies={'pico_bit_session': 'token123'},
    )
    portal._sessions['token123'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    payload = json.loads(body)
    assert '200 OK' in head
    assert payload['run_history'] == [{'sequence': 1, 'notice': 'success', 'preview': 'STRING hi'}]
    assert payload['validation']['blocking'] is False


# ── Rate limiting ────────────────────────────────────────────────────────────

def test_login_lockout_after_max_failed_attempts(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_USERNAME', 'admin')
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    now = [1_000_000]
    monkeypatch.setattr(server, '_ticks_ms', lambda: now[0])

    req = _make_request('POST', '/login', body=b'username=admin&password=wrong')
    writer = FakeWriter()
    for _ in range(server._MAX_LOGIN_ATTEMPTS):
        writer = FakeWriter()
        asyncio.run(portal._handle_login(req, writer))

    assert portal._login_lockout_until > 0


def test_locked_out_login_blocks_post(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_USERNAME', 'admin')
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    now = [1_000_000]
    monkeypatch.setattr(server, '_ticks_ms', lambda: now[0])
    portal._login_lockout_until = server._ticks_add(now[0], server._LOGIN_LOCKOUT_MS)

    writer = FakeWriter()
    asyncio.run(portal._handle_login(
        _make_request('POST', '/login', body=b'username=admin&password=secret'),
        writer,
    ))

    assert '429 Too Many Requests' in writer.text()
    assert 'Try again in' in writer.text()


def test_locked_out_login_shows_wait_on_get(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    now = [1_000_000]
    monkeypatch.setattr(server, '_ticks_ms', lambda: now[0])
    portal._login_lockout_until = server._ticks_add(now[0], server._LOGIN_LOCKOUT_MS)

    writer = FakeWriter()
    asyncio.run(portal._handle_login(_make_request('GET', '/login'), writer))

    assert '200 OK' in writer.text()
    assert 'Try again in' in writer.text()


def test_login_success_resets_lockout_counter(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_USERNAME', 'admin')
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    monkeypatch.setattr(server, '_ticks_ms', lambda: 1_000_000)
    portal._login_attempts = 3

    asyncio.run(portal._handle_login(
        _make_request('POST', '/login', body=b'username=admin&password=secret'),
        FakeWriter(),
    ))

    assert portal._login_attempts == 0
    assert portal._login_lockout_until == 0


# ── Session timeout ───────────────────────────────────────────────────────────

def test_expired_session_is_rejected(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    long_ago = 0
    monkeypatch.setattr(server, '_ticks_ms', lambda: server._SESSION_TIMEOUT_MS + 1)
    portal._sessions['tok'] = 'admin'
    portal._session_timestamps['tok'] = long_ago

    req = _make_request('GET', '/api/bootstrap', cookies={'pico_bit_session': 'tok'})
    assert portal._is_authorized(req) is False
    assert 'tok' not in portal._sessions


def test_active_session_is_not_expired(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    now = 5_000_000
    monkeypatch.setattr(server, '_ticks_ms', lambda: now)
    portal._sessions['tok'] = 'admin'
    portal._session_timestamps['tok'] = now - 60_000  # 1 min ago

    req = _make_request('GET', '/api/bootstrap', cookies={'pico_bit_session': 'tok'})
    assert portal._is_authorized(req) is True


# ── Multi-payload ─────────────────────────────────────────────────────────────

def test_validate_payload_name_accepts_valid() -> None:
    assert server._validate_payload_name('recon') is True
    assert server._validate_payload_name('my-payload_01') is True
    assert server._validate_payload_name('a' * 32) is True


def test_validate_payload_name_rejects_invalid() -> None:
    assert server._validate_payload_name('') is False
    assert server._validate_payload_name('a' * 33) is False
    assert server._validate_payload_name('bad/name') is False
    assert server._validate_payload_name('../escape') is False
    assert server._validate_payload_name('has space') is False


def test_api_payloads_list_empty(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(portal, '_list_payloads', lambda: [])
    request = _make_request('GET', '/api/payloads', cookies={'pico_bit_session': 'tok'})
    portal._sessions['tok'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    assert '200 OK' in head
    assert json.loads(body) == {'payloads': []}


def test_api_payloads_create_valid(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    written: list[tuple[str, str]] = []
    monkeypatch.setattr(portal, '_write_named_payload', lambda n, c: written.append((n, c)))
    request = _make_request(
        'POST', '/api/payloads',
        body=b'{"name": "recon", "payload": "STRING hello\\n"}',
        cookies={'pico_bit_session': 'tok'},
    )
    portal._sessions['tok'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    assert '200 OK' in head
    assert json.loads(body)['name'] == 'recon'
    assert written == [('recon', 'STRING hello\n')]


def test_api_payloads_create_invalid_name(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    request = _make_request(
        'POST', '/api/payloads',
        body=b'{"name": "bad name!", "payload": "STRING hi\\n"}',
        cookies={'pico_bit_session': 'tok'},
    )
    portal._sessions['tok'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    assert '400 Bad Request' in writer.text()


def test_api_payloads_get_content(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    monkeypatch.setattr(portal, '_read_named_payload', lambda n: f'REM {n}\n')
    request = _make_request(
        'GET', '/api/payloads/recon',
        cookies={'pico_bit_session': 'tok'},
    )
    portal._sessions['tok'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    assert '200 OK' in head
    data = json.loads(body)
    assert data['name'] == 'recon'
    assert data['payload'] == 'REM recon\n'


def test_api_payloads_get_missing(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()

    def raise_os(_name):
        raise OSError('no file')

    monkeypatch.setattr(portal, '_read_named_payload', raise_os)
    request = _make_request(
        'GET', '/api/payloads/missing',
        cookies={'pico_bit_session': 'tok'},
    )
    portal._sessions['tok'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    assert '404 Not Found' in writer.text()


def test_api_payloads_delete(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()
    deleted: list[str] = []
    monkeypatch.setattr(portal, '_delete_named_payload', lambda n: deleted.append(n))
    request = _make_request(
        'DELETE', '/api/payloads/recon',
        cookies={'pico_bit_session': 'tok'},
    )
    portal._sessions['tok'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    head, body = writer.text().split('\r\n\r\n', 1)
    assert '200 OK' in head
    assert deleted == ['recon']


def test_api_payloads_delete_missing(monkeypatch) -> None:
    portal = server.SetupServer()
    writer = FakeWriter()

    def raise_os(_name):
        raise OSError('no file')

    monkeypatch.setattr(portal, '_delete_named_payload', raise_os)
    request = _make_request(
        'DELETE', '/api/payloads/ghost',
        cookies={'pico_bit_session': 'tok'},
    )
    portal._sessions['tok'] = 'admin'

    asyncio.run(portal._handle_api(request, writer))

    assert '404 Not Found' in writer.text()


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
