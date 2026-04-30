"""
Entry point for picoDucky (MicroPython / RP2350).

Boot mode is selected by the logic level on GP0 at power-on:

* **GP0 → GND** (setup mode): starts the WiFi AP and web server so you can
  edit ``payload.dd`` over the browser. Connect to the configured setup-mode
  network and open ``http://192.168.4.1``.

* **GP0 floating / high** (payload mode): waits for the USB HID interface to
  be recognised by the host, delays :data:`_INITIAL_DELAY_S` seconds (giving
  the host time to settle), then executes ``payload.dd``.  If the file is
  absent a message is printed and the device idles.

To reprogram the Pico hold the BOOTSEL button while connecting USB (the CDC
REPL is disabled in payload mode because ``builtin_driver`` is set to 0).
"""

import time

import machine

from device_config import EDUCATIONAL_MODE
from ducky import (
    DuckyScriptError,
    find_payload,
    run_script,
    validate_script,
)
from hid import HIDKeyboard
from server import start

# Hold GP0 to GND at boot to enter server / setup mode (same as pico-ducky).
_setup_pin: machine.Pin = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
_INITIAL_DELAY_S: float = 3.0
_EDUCATIONAL_MODE: bool = EDUCATIONAL_MODE

kbd: HIDKeyboard = HIDKeyboard()

if not _setup_pin.value():
    # ── Server mode ──────────────────────────────────────────────────────────
    # Boots WiFi AP, serves web UI at http://192.168.4.1
    # Release GP0 after connecting – it is only read at boot.
    start(kbd)

else:
    # ── Payload mode ─────────────────────────────────────────────────────────
    print('Payload mode: waiting for USB...')
    while not kbd.is_open():
        time.sleep(0.01)

    print(f'USB ready, firing in {_INITIAL_DELAY_S}s...')
    time.sleep(_INITIAL_DELAY_S)

    payload_path = find_payload()
    if payload_path:
        try:
            with open(payload_path) as f:
                script: str = f.read()
            print(f'Running {payload_path}')
            validate_script(script)
            run_script(kbd, script, educational_mode=_EDUCATIONAL_MODE)
        except DuckyScriptError as exc:
            print(f'Payload error: {exc}')
        except OSError:
            print('Unable to read payload.dd.')
            pass
    else:
        print('No payload.dd found.')

    print('Done.')
    while True:
        time.sleep(0.1)
