"""
Entry point for picoDucky (MicroPython / RP2350).

Boot-mode pin: GP22.
  GP22 -> GND  : setup mode (WiFi AP + browser editor at 192.168.4.1)
  GP22 floating: payload mode (executes payload.dd over USB HID)
"""

import machine

from status_led import STATUS_LED

_setup_pin: machine.Pin = machine.Pin(22, machine.Pin.IN, machine.Pin.PULL_UP)
_INITIAL_DELAY_MS: int = 10000

STATUS_LED.show('boot')


def _run() -> None:
    from device_config import EDUCATIONAL_MODE
    from ducky import (
        DuckyScriptError,
        find_payload,
        run_script,
        validate_script,
    )
    from server import start

    if not _setup_pin.value():
        STATUS_LED.show('setup_entered')
        try:
            start()
        except OSError:
            STATUS_LED.halt('setup_ap_failed')
        except Exception:
            STATUS_LED.halt('setup_server_failed')
        return

    from hid import HIDKeyboard

    kbd = HIDKeyboard()
    STATUS_LED.show('hid_constructed')
    STATUS_LED.show('payload_entered')

    STATUS_LED.on()
    if kbd.wait_open(_INITIAL_DELAY_MS):
        STATUS_LED.off()
        STATUS_LED.show('usb_enumerated')
    else:
        STATUS_LED.halt('usb_enum_timeout')
        return

    try:
        payload_path = find_payload()
    except Exception:
        STATUS_LED.halt('payload_find_failed')
        return

    if not payload_path:
        STATUS_LED.halt('payload_missing')
        return

    STATUS_LED.show('payload_ready')
    try:
        with open(payload_path) as f:
            script = f.read()
    except OSError:
        STATUS_LED.halt('payload_read_failed')
        return

    try:
        validate_script(script)
        run_script(kbd, script, educational_mode=EDUCATIONAL_MODE)
    except DuckyScriptError:
        STATUS_LED.halt('script_error')
        return

    STATUS_LED.show('payload_complete')
    while True:
        STATUS_LED.pause(100)


try:
    _run()
except Exception:
    STATUS_LED.halt('unhandled')
