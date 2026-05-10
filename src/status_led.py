"""Centralized LED status patterns for boot stages and fatal errors."""

import machine

from helpers import sleep_ms


class StatusLed:
    STAGE_PATTERNS = {
        'boot': (3, 80, 80, 0),
        'setup_entered': (6, 400, 200, 0),
        'setup_ap_starting': (1, 180, 120, 250),
        'setup_ap_retry': (2, 120, 120, 200),
        'setup_ap_ready': (1, 700, 0, 0),
        'setup_server_ready': (2, 220, 140, 0),
        'hid_constructed': (1, 350, 250, 600),
        'payload_entered': (2, 350, 250, 600),
        'usb_enumerated': (3, 350, 250, 600),
        'payload_ready': (4, 350, 250, 600),
        'payload_running': (3, 120, 90, 180),
        'payload_complete': (2, 500, 300, 0),
        'binary_injecting': (4, 90, 70, 160),
        'binary_inject_failed': (5, 90, 70, 260),
        'safe_mode_changed': (2, 120, 120, 200),
        'keyboard_layout_changed': (3, 80, 80, 220),
        'loot_imported': (3, 180, 80, 120),
        'usb_agent_mounted': (2, 80, 80, 120),
        'usb_agent_unmounted': (1, 260, 0, 120),
    }

    ERROR_PATTERNS = {
        'usb_enum_timeout': (1, 80, 80, 0),
        'script_error': (4, 350, 250, 1500),
        'payload_read_failed': (5, 350, 250, 1500),
        'payload_find_failed': (6, 350, 250, 1500),
        'setup_ap_failed': (7, 350, 250, 1500),
        'setup_server_failed': (8, 350, 250, 1500),
        'unhandled': (9, 80, 80, 1500),
        'payload_missing': (10, 350, 250, 1500),
    }

    def __init__(self, led=None) -> None:
        self._led = led if led is not None else machine.Pin('LED', machine.Pin.OUT)

    async def _blink(self, count: int, on_ms: int, off_ms: int) -> None:
        for _ in range(count):
            self._led.on()
            await sleep_ms(on_ms)
            self._led.off()
            await sleep_ms(off_ms)

    async def show(self, stage: str) -> None:
        """Play a named non-fatal status pattern once."""
        count, on_ms, off_ms, gap_ms = self.STAGE_PATTERNS[stage]
        await self._blink(count, on_ms, off_ms)
        if gap_ms:
            await sleep_ms(gap_ms)

    def on(self) -> None:
        self._led.on()

    def off(self) -> None:
        self._led.off()

    async def pause(self, ms: int) -> None:
        await sleep_ms(ms)

    async def halt(self, error_name: str) -> None:
        """Loop a named fatal pattern forever."""
        count, on_ms, off_ms, gap_ms = self.ERROR_PATTERNS[error_name]
        while True:
            await self._blink(count, on_ms, off_ms)
            if gap_ms:
                await sleep_ms(gap_ms)


STAGE_PATTERNS = StatusLed.STAGE_PATTERNS
ERROR_PATTERNS = StatusLed.ERROR_PATTERNS
STATUS_LED = StatusLed()
