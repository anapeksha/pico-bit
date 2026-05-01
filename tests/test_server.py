from __future__ import annotations

import sys
import types
from typing import Any, cast

import server


def test_page_renders_editor_shell(monkeypatch) -> None:
    monkeypatch.setattr(server, '_read_payload', lambda: 'REM test\nSTRING hi\n')
    monkeypatch.setattr(server, '_ap_password_in_use', server.AP_PASSWORD)

    html = server._page('Saved', 'success')

    assert 'class="editor__chrome"' in html
    assert 'class="editor__input"' in html
    assert 'payload.dd' in html
    assert server.AP_SSID in html
    assert 'Saved' in html


def test_start_ap_uses_micropython_ap_interface_and_key(monkeypatch) -> None:
    events: list[tuple[str, object]] = []

    class FakeWLAN:
        IF_AP = 7
        PM_NONE = 0

        def __init__(self, interface: int) -> None:
            events.append(('init', interface))
            self._active = False

        def config(self, **kwargs) -> None:
            events.append(('config', kwargs))

        def active(self, value: bool | None = None) -> bool:
            if value is not None:
                self._active = value
            return self._active

        def ifconfig(self) -> tuple[str, str, str, str]:
            return ('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8')

    fake_network = types.SimpleNamespace(WLAN=FakeWLAN, AP_IF=3)
    monkeypatch.setattr(server, 'network', fake_network)

    ip = server._start_ap()

    assert ip == '192.168.4.1'
    assert events[0] == ('init', 7)
    assert ('config', {'ssid': server.AP_SSID}) in events
    assert ('config', {'max_clients': server._AP_MAX_CLIENTS}) in events
    assert (
        'config',
        {
            'channel': server._AP_CHANNEL,
            'security': 3,
            'key': server.AP_PASSWORD,
        },
    ) in events
    assert ('config', {'pm': 0}) in events


def test_start_ap_falls_back_to_open_network(monkeypatch) -> None:
    events: list[tuple[str, object]] = []

    class FakeWLAN:
        IF_AP = 5
        PM_NONE = 0
        SEC_OPEN = 0
        SEC_WPA2 = 3
        SEC_WPA_WPA2 = 4

        def __init__(self, _interface: int) -> None:
            self._active = False

        def config(self, **kwargs) -> None:
            events.append(('config', kwargs))
            if 'key' in kwargs or 'password' in kwargs:
                raise TypeError('secured AP config unsupported')

        def active(self, value: bool | None = None) -> bool:
            if value is not None:
                self._active = value
            return self._active

        def ifconfig(self) -> tuple[str, str, str, str]:
            return ('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8')

    fake_network = types.SimpleNamespace(WLAN=FakeWLAN, AP_IF=3)
    monkeypatch.setattr(server, 'network', fake_network)
    monkeypatch.setattr(server, '_ap_password_in_use', server.AP_PASSWORD)

    ip = server._start_ap()

    assert ip == '192.168.4.1'
    assert server._ap_password_in_use == ''
    assert ('config', {'ssid': server.AP_SSID}) in events
    assert (
        'config',
        {'channel': server._AP_CHANNEL, 'security': 0},
    ) in events


def test_start_ap_can_retry_with_active_first(monkeypatch) -> None:
    class FakeWLAN:
        IF_AP = 9
        PM_NONE = 0
        SEC_WPA2 = 3

        def __init__(self, _interface: int) -> None:
            self._active = False

        def config(self, **kwargs) -> None:
            if 'pm' in kwargs:
                return
            if not self._active:
                raise OSError('must activate AP before config on this firmware')

        def active(self, value: bool | None = None) -> bool:
            if value is not None:
                self._active = value
            return self._active

        def ifconfig(self) -> tuple[str, str, str, str]:
            return ('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8')

    fake_network = types.SimpleNamespace(WLAN=FakeWLAN, AP_IF=3)
    monkeypatch.setattr(server, 'network', fake_network)

    ip = server._start_ap()

    assert ip == '192.168.4.1'


def test_wait_for_ap_returns_default_ip_when_interface_is_active(monkeypatch) -> None:
    class FakeWLAN:
        def active(self, value: bool | None = None) -> bool:
            return True

        def ifconfig(self) -> tuple[str, str, str, str]:
            raise OSError('ip config not ready yet')

    monkeypatch.setattr(server, '_sleep_ms', lambda _ms: None)

    ip = server._wait_for_ap(cast(Any, FakeWLAN()))

    assert ip == server._DEFAULT_AP_IP


def test_ensure_keyboard_is_lazy(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    class FakeKeyboard:
        def wait_open(self, timeout_ms: int) -> bool:
            calls.append(('wait_open', timeout_ms))
            return True

    fake_hid = types.SimpleNamespace(HIDKeyboard=FakeKeyboard)
    monkeypatch.setitem(sys.modules, 'hid', fake_hid)
    monkeypatch.setattr(server, '_kbd', None)

    keyboard = server._ensure_keyboard()

    assert isinstance(keyboard, FakeKeyboard)
    assert calls == [('wait_open', server._USB_ENUM_TIMEOUT_MS)]
