import asyncio

from helpers import wait_forever
from status_led import STATUS_LED

_INITIAL_DELAY_MS: int = 10000


async def _start_server():
    try:
        from server import SERVER

        await SERVER.start()
        return SERVER
    except OSError:
        await STATUS_LED.halt('setup_ap_failed')
    except Exception:
        await STATUS_LED.halt('setup_server_failed')

    raise AssertionError('unreachable')


async def _run_payload(server) -> str | None:
    from ducky import DuckyScriptError, ensure_payload, validate_script

    await STATUS_LED.show('payload_entered')

    try:
        payload_path, _ = ensure_payload()
    except Exception:
        return 'payload_find_failed'

    if not payload_path:
        return 'payload_missing'

    try:
        with open(payload_path) as f:
            script = f.read()
    except OSError:
        return 'payload_read_failed'

    try:
        keyboard = server.keyboard()
        await STATUS_LED.show('hid_constructed')
        STATUS_LED.on()
        keyboard_ready = await keyboard.wait_open(_INITIAL_DELAY_MS)
        if not keyboard_ready:
            return 'usb_enum_timeout'

        STATUS_LED.off()
        await STATUS_LED.show('usb_enumerated')
        await STATUS_LED.show('payload_ready')
        validate_script(script)
        await server.execute_script(script)
    except DuckyScriptError:
        return 'script_error'
    except OSError:
        return 'usb_enum_timeout'

    await STATUS_LED.show('payload_complete')
    return None


async def run() -> None:
    await STATUS_LED.show('boot')
    server = await _start_server()
    error_name = await _run_payload(server)
    if error_name is not None:
        await STATUS_LED.halt(error_name)
        return
    await wait_forever()


try:
    asyncio.run(run())
except Exception:
    asyncio.run(STATUS_LED.halt('unhandled'))
