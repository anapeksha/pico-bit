import asyncio
import time

if hasattr(time, 'sleep_ms'):
    sleep_ms_blocking = time.sleep_ms  # type: ignore[attr-defined]
else:

    def sleep_ms_blocking(ms: int) -> None:
        time.sleep(ms / 1000)


_asyncio_sleep_ms = getattr(asyncio, 'sleep_ms', None)

def sleep_ms(ms: int):
    if _asyncio_sleep_ms is not None:
        return _asyncio_sleep_ms(ms)
    return asyncio.sleep(ms / 1000)


async def maybe_wait_closed(target) -> None:
    wait_closed = getattr(target, 'wait_closed', None)
    if wait_closed is None:
        return
    result = wait_closed()
    if result is not None:
        await result


async def wait_forever() -> None:
    while True:
        await sleep_ms(100)
