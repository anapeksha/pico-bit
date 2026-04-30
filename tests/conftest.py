from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


machine = cast(Any, types.ModuleType('machine'))


class Pin:
    IN = 0
    OUT = 1
    PULL_UP = 2

    def __init__(self, *_args, **_kwargs):
        self._value = 1

    def value(self, new_value: int | None = None) -> int:
        if new_value is not None:
            self._value = new_value
        return self._value


class USBDevice:
    BUILTIN_NONE = 0

    def __init__(self):
        self.builtin_driver = 0

    def config(self, *_args, **_kwargs) -> None:
        pass

    def active(self, _value: bool) -> None:
        pass

    def submit_xfer(self, _endpoint: int, _data) -> None:
        pass


machine.Pin = Pin
machine.USBDevice = USBDevice
sys.modules.setdefault('machine', machine)


network = cast(Any, types.ModuleType('network'))


class WLAN:
    def __init__(self, _interface: int):
        self._active = False

    def active(self, value: bool | None = None) -> bool:
        if value is not None:
            self._active = value
        return self._active

    def config(self, **_kwargs) -> None:
        pass

    def ifconfig(self) -> tuple[str, str, str, str]:
        return ('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8')


network.AP_IF = 0
network.WLAN = WLAN
sys.modules.setdefault('network', network)
