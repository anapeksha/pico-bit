"""Small publish/subscribe state for one-way loot updates.

This is intentionally simpler than WebSockets:
- one direction only: Pico -> portal
- no framing, masking, or upgrade handshake
- tiny in-memory state that fits the existing server model

Each publish swaps the internal event object so listeners can wait for the
next revision without clearing shared state for other clients.
"""

import asyncio


class LootStreamState:
    def __init__(self) -> None:
        self._revision = 0
        self._payload = ''
        self._event = asyncio.Event()

    def snapshot(self) -> tuple[int, str]:
        """Return the latest revision number and serialized payload."""
        return self._revision, self._payload

    def waiter(self):
        """Return an event that becomes set on the next publish."""
        return self._event

    def publish(self, payload: str) -> int:
        """Publish a new serialized payload and wake current listeners."""
        self._payload = payload
        self._revision += 1
        current_event = self._event
        self._event = asyncio.Event()
        current_event.set()
        return self._revision
