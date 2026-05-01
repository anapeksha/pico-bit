from __future__ import annotations

import sys
import types

import pytest

import server


def test_singleton_is_exported() -> None:
    assert isinstance(server.SERVER, server.SetupServer)


def test_page_renders_editor_shell(monkeypatch) -> None:
    portal = server.SetupServer()
    monkeypatch.setattr(portal, '_read_payload', lambda: 'REM test\nSTRING hi\n')
    portal._ap_password_in_use = server.AP_PASSWORD

    html = portal._page('Saved', 'success')

    assert 'class="editor__chrome"' in html
    assert 'class="editor__input"' in html
    assert 'payload.dd' in html
    assert server.AP_SSID in html
    assert 'Saved' in html


def test_start_background_starts_server_thread_once(monkeypatch) -> None:
    events: list[object] = []
    portal = server.SetupServer()

    class FakeThread:
        def start_new_thread(self, target, args) -> None:
            events.append(('thread', target, args))

    monkeypatch.setattr(portal, '_prepare_server', lambda: events.append('prepare'))
    monkeypatch.setattr(portal, '_thread_module', lambda: FakeThread())

    portal.start_background()
    portal.start_background()

    assert events == ['prepare', ('thread', portal._serve_forever, ())]


def _make_fake_network(fake_wlan_cls):
    return types.SimpleNamespace(WLAN=fake_wlan_cls, AP_IF=3)


def test_start_ap_configures_essid_and_password_before_activate(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    portal = server.SetupServer()

    class FakeWLAN:
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
    monkeypatch.setattr(server, '_sleep_ms', lambda _ms: None)

    ip = portal._start_ap()

    assert ip == '192.168.4.1'
    assert portal._ap is not None
    assert events[0] == ('init', 3)

    config_index = next(
        i for i, ev in enumerate(events) if ev[0] == 'config' and 'essid' in ev[1]
    )
    activate_index = next(
        i for i, ev in enumerate(events) if ev == ('active', True)
    )
    assert config_index < activate_index, 'config must run before active(True)'
    assert events[config_index][1] == {
        'essid': server.AP_SSID,
        'password': server.AP_PASSWORD,
    }


def test_start_ap_omits_password_when_blank(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    portal = server.SetupServer()

    class FakeWLAN:
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
    monkeypatch.setattr(server, '_sleep_ms', lambda _ms: None)

    ip = portal._start_ap()

    assert ip == '192.168.4.1'
    assert portal._ap_password_in_use == ''
    assert ('config', {'essid': server.AP_SSID}) in events
    assert all('password' not in ev[1] for ev in events if ev[0] == 'config')


def test_start_ap_raises_when_interface_never_activates(monkeypatch) -> None:
    portal = server.SetupServer()

    class FakeWLAN:
        def __init__(self, _interface: int) -> None:
            self._active = False

        def config(self, **kwargs) -> None:
            pass

        def active(self, value: bool | None = None) -> bool:
            return False

        def ifconfig(self) -> tuple[str, str, str, str]:
            return ('0.0.0.0', '', '', '')

    monkeypatch.setattr(server, 'network', _make_fake_network(FakeWLAN))
    monkeypatch.setattr(server, '_sleep_ms', lambda _ms: None)

    with pytest.raises(OSError, match='AP failed to come active'):
        portal._start_ap()


def test_start_ap_returns_default_ip_when_ifconfig_unavailable(monkeypatch) -> None:
    portal = server.SetupServer()

    class FakeWLAN:
        def __init__(self, _interface: int) -> None:
            self._active = False

        def config(self, **kwargs) -> None:
            pass

        def active(self, value: bool | None = None) -> bool:
            if value is not None:
                self._active = value
            return self._active

        def ifconfig(self) -> tuple[str, str, str, str]:
            raise OSError('ip not yet assigned')

    monkeypatch.setattr(server, 'network', _make_fake_network(FakeWLAN))
    monkeypatch.setattr(server, '_sleep_ms', lambda _ms: None)

    ip = portal._start_ap()

    assert ip == server._DEFAULT_AP_IP


def test_ensure_keyboard_is_lazy(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []
    portal = server.SetupServer()

    class FakeKeyboard:
        def wait_open(self, timeout_ms: int) -> bool:
            calls.append(('wait_open', timeout_ms))
            return True

    fake_hid = types.SimpleNamespace(HIDKeyboard=FakeKeyboard)
    monkeypatch.setitem(sys.modules, 'hid', fake_hid)
    portal._kbd = None

    keyboard = portal._ensure_keyboard()

    assert isinstance(keyboard, FakeKeyboard)
    assert calls == [('wait_open', server._USB_ENUM_TIMEOUT_MS)]


def test_execute_script_serializes_hid_use(monkeypatch) -> None:
    events: list[object] = []
    portal = server.SetupServer()
    fake_keyboard = object()

    class FakeLock:
        def acquire(self) -> None:
            events.append('acquire')

        def release(self) -> None:
            events.append('release')

    class FakeThread:
        def allocate_lock(self):
            return FakeLock()

    monkeypatch.setattr(portal, '_thread_module', lambda: FakeThread())
    monkeypatch.setattr(portal, '_ensure_keyboard', lambda: fake_keyboard)
    monkeypatch.setattr(
        server,
        'validate_script',
        lambda script: events.append(('validate', script)),
    )
    monkeypatch.setattr(
        server,
        'run_script',
        lambda keyboard, script, allow_unsafe=False: events.append(
            ('run', keyboard, script, allow_unsafe)
        ),
    )

    portal.execute_script('STRING hi\n', allow_unsafe=True)

    assert events == [
        'acquire',
        ('validate', 'STRING hi\n'),
        ('run', fake_keyboard, 'STRING hi\n', True),
        'release',
    ]
