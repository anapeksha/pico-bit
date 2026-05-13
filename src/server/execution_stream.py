"""Publish/subscribe state for one-way execution-step updates during binary injection.

Each publish appends an event to the log so any SSE client that (re)connects
mid-run can replay from the beginning of the current session.  The log is
replaced on reset so memory does not grow across injection sessions.
"""

from asyncio import Event


class ExecutionStreamState:
    def __init__(self) -> None:
        self._events: list[dict[str, str]] = []
        self._complete = False
        self._awaiting_loot = False
        self._event = Event()

    def _wake(self) -> None:
        old = self._event
        self._event = Event()
        old.set()

    def events_from(self, idx: int) -> list[dict[str, str]]:
        """Return all events that have not yet been sent to a client at *idx*."""
        return self._events[idx:]

    def publish(self, step: str, state: str, reason: str = '') -> None:
        self._events.append({'step': step, 'state': state, 'reason': reason})
        if step == 'Execute' and state == 'loading':
            self._awaiting_loot = True
        if state == 'error':
            self._complete = True
        self._wake()

    def on_loot_received(self) -> None:
        """Called when an agent loot payload arrives.  Completes the run."""
        if not self._awaiting_loot:
            return
        self._awaiting_loot = False
        self._events.append({'step': 'Collect', 'state': 'success', 'reason': ''})
        self._events.append({'step': 'Cleanup', 'state': 'success', 'reason': ''})
        self._complete = True
        self._wake()

    def reset(self) -> None:
        self._events = []
        self._complete = False
        self._awaiting_loot = False
        self._event = Event()

    def is_complete(self) -> bool:
        return self._complete

    def is_awaiting_loot(self) -> bool:
        return self._awaiting_loot

    def waiter(self) -> Event:
        return self._event
