from __future__ import annotations

import asyncio
import json
import sys
import types
from typing import Any, cast

import pytest

import server
import server.micro_server as _micro_server
from _test_client import TestClient


def test_singleton_is_exported() -> None:
    assert isinstance(server.SERVER, server.SetupServer)


def test_login_page_renders_form() -> None:
    portal = server.SetupServer()

    html = portal._render_login('Nope', username='ana')

    assert 'Unlock' in html
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
    assert state['keyboard_layout_code'] == 'US'
    assert state['keyboard_layout_label'] == 'English (US)'
    assert state['keyboard_layout_profile_code'] == 'WIN_US'
    assert state['keyboard_os_code'] == 'WIN'
    assert state['keyboard_target_label'] == 'Windows · English (US)'
    assert state['message'] == 'payload.dd was seeded on this boot.'


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

    async def fake_run_script(keyboard, script, default_layout='WIN_US'):
        events.append(('run', keyboard, script, default_layout))

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

    asyncio.run(portal.execute_script('STRING hi\n'))

    assert events == [
        'acquire',
        ('validate', 'STRING hi\n'),
        ('led', 'payload_running'),
        ('run', fake_keyboard, 'STRING hi\n', 'WIN_DE'),
        'release',
    ]


def test_run_payload_records_recent_history(monkeypatch) -> None:
    portal = server.SetupServer()

    async def fake_execute_script(script: str) -> None:
        assert script == 'STRING hi\n'

    monkeypatch.setattr(portal, 'execute_script', fake_execute_script)

    message, notice = asyncio.run(portal._run_payload('STRING hi\n'))

    assert (message, notice) == ('Payload executed.', 'success')
    assert portal._run_history[0]['source'] == 'portal'
    assert portal._run_history[0]['preview'] == 'STRING hi'


def test_dispatch_redirects_to_login_when_not_authorized(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/'))

    assert res.status_code == 303
    assert res.headers.get('Location') == '/login'


def test_dispatch_serves_assets_without_auth() -> None:
    portal = server.SetupServer()
    client = TestClient(portal.app)

    res = asyncio.run(client.get('/assets/portal.js'))

    assert res.status_code == 200
    assert 'application/javascript' in res.headers.get('Content-Type', '')
    assert 'loadBootstrap' in (res.text or '')


def test_login_success_sets_cookie(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_USERNAME', 'admin')
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    monkeypatch.setattr(portal.auth, 'login', lambda username: 'token123')

    client = TestClient(portal.app)
    res = asyncio.run(client.post('/login', body=b'username=admin&password=secret'))

    assert res.status_code == 303
    assert client.cookies.get('pico_bit_session') == 'token123'


def test_api_bootstrap_returns_json_when_authorized(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(portal, '_bootstrap_state', lambda: {'payload': 'REM hi\n'})
    portal.auth._sessions['token123'] = 'admin'

    client = TestClient(portal.app, cookies={'pico_bit_session': 'token123'})
    res = asyncio.run(client.get('/api/bootstrap'))

    assert res.status_code == 200
    assert 'application/json' in res.headers.get('Content-Type', '')
    assert res.json is not None
    assert res.json['payload'] == 'REM hi\n'


def test_api_keyboard_layout_updates_runtime_state(monkeypatch) -> None:
    portal = server.SetupServer()
    events: list[str] = []
    persisted: list[str] = []
    monkeypatch.setattr(portal, '_persist_keyboard_layout', lambda code: persisted.append(code))
    monkeypatch.setattr(
        server.STATUS_LED,
        'show',
        lambda stage: asyncio.sleep(0, result=events.append(stage)),
    )
    portal.auth._sessions['token123'] = 'admin'

    client = TestClient(portal.app, cookies={'pico_bit_session': 'token123'})
    res = asyncio.run(client.post('/api/keyboard-layout', body=b'{"os": "WIN", "layout": "DE"}'))

    assert res.status_code == 200
    assert portal._keyboard_layout == 'WIN_DE'
    assert res.json is not None
    assert res.json['keyboard_layout_code'] == 'DE'
    assert res.json['keyboard_layout_label'] == 'German (DE)'
    assert res.json['keyboard_layout_profile_code'] == 'WIN_DE'
    assert res.json['keyboard_os_code'] == 'WIN'
    assert res.json['message'] == 'Typing target set to Windows · German (DE).'
    assert persisted == ['WIN_DE']
    assert events == ['keyboard_layout_changed']


def test_api_keyboard_layout_switches_os_and_uses_platform_default(monkeypatch) -> None:
    portal = server.SetupServer()
    portal._keyboard_layout = 'WIN_DE'
    persisted: list[str] = []
    monkeypatch.setattr(portal, '_persist_keyboard_layout', lambda code: persisted.append(code))
    monkeypatch.setattr(server.STATUS_LED, 'show', lambda _stage: asyncio.sleep(0))
    portal.auth._sessions['token123'] = 'admin'

    client = TestClient(portal.app, cookies={'pico_bit_session': 'token123'})
    res = asyncio.run(client.post('/api/keyboard-layout', body=b'{"os": "MAC"}'))

    assert res.status_code == 200
    assert portal._keyboard_layout == 'MAC_US'
    assert res.json is not None
    assert res.json['keyboard_os_code'] == 'MAC'
    assert res.json['keyboard_layout_code'] == 'US'
    assert res.json['keyboard_layouts'] == [
        {'code': 'US', 'label': 'English (US)'},
        {'code': 'FR', 'label': 'French (FR)'},
    ]
    assert res.json['message'] == 'Typing target set to macOS · English (US).'
    assert persisted == ['MAC_US']


def test_api_keyboard_layout_rejects_unknown_value() -> None:
    portal = server.SetupServer()
    portal.auth._sessions['token123'] = 'admin'

    client = TestClient(portal.app, cookies={'pico_bit_session': 'token123'})
    res = asyncio.run(client.post('/api/keyboard-layout', body=b'{"os": "MAC", "layout": "DE"}'))

    assert res.status_code == 400
    assert res.json is not None
    assert res.json['message'] == 'Unsupported keyboard layout for macOS.'


def test_api_validate_returns_dry_run_state(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(
        portal,
        '_validation_state',
        lambda script: {'blocking': False, 'summary': f'validated {script}', 'notice': 'success'},
    )
    portal.auth._sessions['token123'] = 'admin'

    client = TestClient(portal.app, cookies={'pico_bit_session': 'token123'})
    res = asyncio.run(client.post('/api/validate', body=b'{"payload": "STRING hi\\n"}'))

    assert res.status_code == 200
    assert res.json is not None
    assert res.json['message'] == 'validated STRING hi\n'
    assert res.json['validation']['blocking'] is False


def test_api_payload_rejects_blocking_validation(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(
        portal,
        '_validation_state',
        lambda _script: {'blocking': True, 'summary': 'Fix 1 error.', 'notice': 'error'},
    )
    portal.auth._sessions['token123'] = 'admin'

    client = TestClient(portal.app, cookies={'pico_bit_session': 'token123'})
    res = asyncio.run(client.post('/api/payload', body=b'{"payload": "WAIT_FOR_CAPS_ON\\n"}'))

    assert res.status_code == 400
    assert res.json is not None
    assert res.json['message'] == 'Fix 1 error.'
    assert res.json['validation']['blocking'] is True


def test_api_run_returns_recent_history(monkeypatch) -> None:
    portal = server.SetupServer()
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
    portal.auth._sessions['token123'] = 'admin'

    client = TestClient(portal.app, cookies={'pico_bit_session': 'token123'})
    res = asyncio.run(client.post('/api/run', body=b'{"payload": "STRING hi\\n", "save": true}'))

    assert res.status_code == 200
    assert res.json is not None
    assert res.json['run_history'] == [{'sequence': 1, 'notice': 'success', 'preview': 'STRING hi'}]
    assert res.json['validation']['blocking'] is False


# ── Rate limiting ────────────────────────────────────────────────────────────


def test_login_lockout_after_max_failed_attempts(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_USERNAME', 'admin')
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')

    async def run() -> None:
        client = TestClient(portal.app)
        for _ in range(server._MAX_LOGIN_ATTEMPTS):
            await client.post('/login', body=b'username=admin&password=wrong')

    asyncio.run(run())
    assert portal.auth._lockout_until > 0


def test_locked_out_login_blocks_post(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_USERNAME', 'admin')
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    now = [1_000_000]
    monkeypatch.setattr(_micro_server, '_ticks_ms', lambda: now[0])
    portal.auth._lockout_until = now[0] + server._LOGIN_LOCKOUT_MS

    client = TestClient(portal.app)
    res = asyncio.run(client.post('/login', body=b'username=admin&password=secret'))

    assert res.status_code == 429
    assert res.text is not None
    assert 'Try again in' in res.text


def test_locked_out_login_shows_wait_on_get(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    now = [1_000_000]
    monkeypatch.setattr(_micro_server, '_ticks_ms', lambda: now[0])
    portal.auth._lockout_until = now[0] + server._LOGIN_LOCKOUT_MS

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/login'))

    assert res.status_code == 200
    assert res.text is not None
    assert 'Try again in' in res.text


def test_login_success_resets_lockout_counter(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_USERNAME', 'admin')
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    portal.auth._attempts = 3

    client = TestClient(portal.app)
    asyncio.run(client.post('/login', body=b'username=admin&password=secret'))

    assert portal.auth._attempts == 0
    assert portal.auth._lockout_until == 0


# ── Session timeout ───────────────────────────────────────────────────────────


def test_expired_session_is_rejected(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    long_ago = 0
    monkeypatch.setattr(_micro_server, '_ticks_ms', lambda: server._SESSION_TIMEOUT_MS + 1)
    portal.auth._sessions['tok'] = 'admin'
    portal.auth._timestamps['tok'] = long_ago

    req = types.SimpleNamespace(cookies={'pico_bit_session': 'tok'})
    assert portal.auth._check_session(req) is None
    assert 'tok' not in portal.auth._sessions


def test_active_session_is_not_expired(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.setattr(server, 'PORTAL_PASSWORD', 'secret')
    now = 5_000_000
    monkeypatch.setattr(_micro_server, '_ticks_ms', lambda: now)
    portal.auth._sessions['tok'] = 'admin'
    portal.auth._timestamps['tok'] = now - 60_000

    req = types.SimpleNamespace(cookies={'pico_bit_session': 'tok'})
    assert portal.auth._check_session(req) is not None


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


# ── Stager script ─────────────────────────────────────────────────────────────


def test_stager_windows_uses_hidden_window_and_pico_agent_name() -> None:
    portal = server.SetupServer()
    portal._ap_ip = '192.168.4.1'
    script = portal._stager_script('windows')
    assert '-w hidden' in script
    assert 'pico_agent.exe' in script
    assert '/static/payload.bin' in script
    assert 'GUI r' in script


def test_stager_linux_uses_background_exec_and_pico_agent_name() -> None:
    portal = server.SetupServer()
    portal._ap_ip = '192.168.4.1'
    script = portal._stager_script('linux')
    assert 'pico_agent' in script
    assert '/static/payload.bin' in script
    assert '/tmp/pico_agent &' in script  # background execution
    assert 'CTRL-ALT t' in script


def test_stager_macos_opens_terminal_and_uses_pico_agent_name() -> None:
    portal = server.SetupServer()
    portal._ap_ip = '192.168.4.1'
    script = portal._stager_script('macos')
    assert 'pico_agent' in script
    assert '/static/payload.bin' in script
    assert 'Terminal' in script


# ── Loot receive ──────────────────────────────────────────────────────────────


def test_loot_receive_saves_json(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.chdir(tmp_path)

    payload = json.dumps({'type': 'recon', 'system': {'hostname': 'victim'}})
    client = TestClient(portal.app)
    res = asyncio.run(client.post('/api/loot', body=payload.encode()))

    assert res.status_code == 200
    saved = json.loads((tmp_path / 'loot.json').read_text())
    assert saved['system']['hostname'] == 'victim'


def test_loot_receive_rejects_invalid_json(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.chdir(tmp_path)

    client = TestClient(portal.app)
    res = asyncio.run(client.post('/api/loot', body=b'not json!!!'))

    assert res.status_code == 400


# ── Loot GET ──────────────────────────────────────────────────────────────────


def test_api_loot_get_returns_saved_data(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'loot.json').write_text('{"type":"exfil"}')

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/api/loot'))

    assert res.status_code == 200
    assert res.text is not None
    assert 'exfil' in res.text


def test_api_loot_get_returns_404_when_missing(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/api/loot'))

    assert res.status_code == 404


def test_api_loot_download_returns_attachment_header(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'loot.json').write_text('{"type":"recon"}')

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/api/loot/download'))

    assert res.status_code == 200
    assert 'attachment' in res.headers.get('Content-Disposition', '')
    assert 'loot.json' in res.headers.get('Content-Disposition', '')
    assert res.text is not None
    assert 'recon' in res.text


def test_api_loot_download_returns_404_when_missing(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/api/loot/download'))

    assert res.status_code == 404


# ── Binary upload ─────────────────────────────────────────────────────────────


def test_upload_binary_writes_to_static_payload_bin(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)

    body = b'\x7fELF' + b'\x00' * 60

    client = TestClient(portal.app)
    res = asyncio.run(
        client.post(
            '/api/upload_binary',
            headers={'X-Filename': 'recon', 'Content-Type': 'application/octet-stream'},
            body=body,
        )
    )

    assert res.status_code == 200
    written = (tmp_path / 'static' / 'payload.bin').read_bytes()
    assert written == body


def test_upload_binary_rejects_oversized_body(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)

    big = server._MAX_BINARY_SIZE + 1

    async def run():
        client = TestClient(portal.app)
        # Spoof Content-Length; Microdot rejects before body is read
        return await client.request(
            'POST',
            '/api/upload_binary',
            headers={
                'Content-Length': str(big),
                'Content-Type': 'application/octet-stream',
            },
            body=b'',
        )

    res = asyncio.run(run())
    assert res.status_code == 413


# ── has_binary / static serve ─────────────────────────────────────────────────


def test_has_binary_false_when_no_file(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.chdir(tmp_path)
    assert portal._has_binary() is False


def test_has_binary_true_after_upload(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'static').mkdir()
    (tmp_path / 'static' / 'payload.bin').write_bytes(b'\x00')
    assert portal._has_binary() is True


def test_serve_payload_returns_binary(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'static').mkdir()
    (tmp_path / 'static' / 'payload.bin').write_bytes(b'\xca\xfe\xba\xbe')

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/static/payload.bin'))

    assert res.status_code == 200
    assert res.body is not None
    assert b'\xca\xfe\xba\xbe' in res.body
    assert 'application/octet-stream' in res.headers.get('Content-Type', '')


def test_serve_payload_404_when_missing(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.chdir(tmp_path)

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/static/payload.bin'))

    assert res.status_code == 404


def test_serve_payload_requires_no_auth(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'static').mkdir()
    (tmp_path / 'static' / 'payload.bin').write_bytes(b'\xde\xad\xbe\xef')

    client = TestClient(portal.app)
    res = asyncio.run(client.get('/static/payload.bin'))

    assert res.status_code == 200
    assert res.body is not None
    assert b'\xde\xad\xbe\xef' in res.body


# ── Inject binary ─────────────────────────────────────────────────────────────


def test_inject_binary_returns_404_when_no_binary_staged(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)

    client = TestClient(portal.app)
    res = asyncio.run(client.post('/api/inject_binary', body=b'{"os":"windows"}'))

    assert res.status_code == 404


def test_inject_binary_runs_stager_and_returns_run_history(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'static').mkdir()
    (tmp_path / 'static' / 'payload.bin').write_bytes(b'\x7fELF')

    scripts_run: list[str] = []

    async def fake_run(script: str) -> tuple[str, str]:
        scripts_run.append(script)
        return ('Payload executed.', 'success')

    monkeypatch.setattr(portal, '_run_payload', fake_run)

    client = TestClient(portal.app)
    res = asyncio.run(client.post('/api/inject_binary', body=b'{"os":"windows"}'))

    assert res.status_code == 200
    assert scripts_run
    assert 'GUI r' in scripts_run[0]
    assert '/static/payload.bin' in scripts_run[0]
    assert res.json is not None
    assert 'run_history' in res.json


def test_inject_binary_defaults_to_windows_when_os_omitted(tmp_path, monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(server, 'PORTAL_AUTH_ENABLED', False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'static').mkdir()
    (tmp_path / 'static' / 'payload.bin').write_bytes(b'\x7fELF')

    scripts_run: list[str] = []

    async def fake_run(script: str) -> tuple[str, str]:
        scripts_run.append(script)
        return ('Payload executed.', 'success')

    monkeypatch.setattr(portal, '_run_payload', fake_run)

    client = TestClient(portal.app)
    asyncio.run(client.post('/api/inject_binary', body=b'{}'))

    assert scripts_run
    assert 'pico_agent.exe' in scripts_run[0]
