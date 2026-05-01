from status_led import STATUS_LED

_INITIAL_DELAY_MS: int = 10000

STATUS_LED.show('boot')


def _start_server() -> None:
    try:
        from server import SERVER

        SERVER.start_background()
    except OSError:
        STATUS_LED.halt('setup_ap_failed')
    except Exception:
        STATUS_LED.halt('setup_server_failed')


def _run_payload_mode() -> None:
    from device_config import ALLOW_UNSAFE
    from ducky import (
        DuckyScriptError,
        find_payload,
        run_script,
        validate_script,
    )
    from server import SERVER

    _start_server()
    STATUS_LED.show('payload_entered')

    try:
        payload_path = find_payload()
    except Exception:
        STATUS_LED.halt('payload_find_failed')
        return

    if not payload_path:
        STATUS_LED.halt('payload_missing')
        return

    try:
        with open(payload_path) as f:
            script = f.read()
    except OSError:
        STATUS_LED.halt('payload_read_failed')
        return

    keyboard_ready = False
    try:
        SERVER.acquire_execution()
        try:
            kbd = SERVER.keyboard()
            STATUS_LED.show('hid_constructed')
            STATUS_LED.on()
            keyboard_ready = kbd.wait_open(_INITIAL_DELAY_MS)
            if keyboard_ready:
                STATUS_LED.off()
                STATUS_LED.show('usb_enumerated')
                STATUS_LED.show('payload_ready')
                validate_script(script)
                run_script(kbd, script, allow_unsafe=ALLOW_UNSAFE)
        finally:
            SERVER.release_execution()
    except DuckyScriptError:
        STATUS_LED.halt('script_error')
        return

    if not keyboard_ready:
        STATUS_LED.halt('usb_enum_timeout')
        return

    STATUS_LED.show('payload_complete')
    while True:
        STATUS_LED.pause(100)


def run() -> None:
    _run_payload_mode()


try:
    run()
except Exception:
    STATUS_LED.halt('unhandled')
