import gc
import json

from helpers import sleep_ms

from ._http import _JSON_HEADERS, _LOOT_FILE, _NO_STORE, _merge_headers, _ticks_ms
from .loot_stream import LootStreamState
from .sse import sse_comment, sse_event

_LOOT_STREAM_HEARTBEAT_MS = 15_000
_LOOT_STREAM_STEP_MS = 250


class _LootMixin:
    # Attributes provided by SetupServer.__init__
    _loot_stream: LootStreamState

    # Methods provided by SetupServer
    async def _send(self, writer, request, status: str, body, headers=None) -> None: ...
    async def _send_headers(self, writer, request, status: str, headers=None) -> None: ...
    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None: ...

    def _normalize_loot_record(self, data) -> dict[str, object]:
        record = dict(data) if isinstance(data, dict) else {'payload': data}
        record['timestamp'] = _ticks_ms()
        return record

    def _serialize_loot_record(self, record: dict[str, object]) -> str:
        return json.dumps(record)

    def _read_loot_text(self) -> str:
        with open(_LOOT_FILE) as f:
            return f.read()

    def _publish_loot_text(self, text: str) -> int:
        return self._loot_stream.publish(text)

    async def _handle_loot_receive(self, request, writer) -> None:
        gc.collect()
        try:
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
        except ValueError:
            await self._send_json(writer, request, '400 Bad Request', {'message': 'Invalid JSON.'})
            return
        record = self._normalize_loot_record(data)
        text = self._serialize_loot_record(record)
        try:
            gc.collect()
            with open(_LOOT_FILE, 'w') as f:
                f.write(text)
        except (OSError, MemoryError):
            await self._send_json(
                writer, request, '500 Internal Server Error', {'message': 'Write failed.'}
            )
            return
        self._publish_loot_text(text)
        await self._send_json(
            writer,
            request,
            '200 OK',
            {'message': 'Loot saved.', 'timestamp': record['timestamp']},
        )

    async def _handle_loot_get(self, request, writer) -> None:
        try:
            text = self._read_loot_text()
        except OSError:
            await self._send_json(
                writer,
                request,
                '404 Not Found',
                {'message': 'No loot collected yet.'},
            )
            return
        await self._send(
            writer,
            request,
            '200 OK',
            text.encode(),
            headers=_merge_headers(_JSON_HEADERS, _NO_STORE),
        )

    async def _handle_loot_download(self, request, writer) -> None:
        try:
            text = self._read_loot_text()
        except OSError:
            await self._send_json(
                writer,
                request,
                '404 Not Found',
                {'message': 'No loot collected yet.'},
            )
            return
        await self._send(
            writer,
            request,
            '200 OK',
            text.encode(),
            headers=_merge_headers(
                _JSON_HEADERS,
                {'Content-Disposition': 'attachment; filename="loot.json"'},
                _NO_STORE,
            ),
        )

    async def _handle_loot_stream(self, request, writer) -> None:
        """Stream loot updates over SSE.

        SSE is a better fit than WebSockets here:
        - the browser only needs one-way updates
        - the Pico avoids websocket upgrade + frame handling
        - EventSource reconnects automatically if the AP bounces
        """
        await self._send_headers(
            writer,
            request,
            '200 OK',
            headers=_merge_headers(
                {
                    'Cache-Control': 'no-store',
                    'Content-Type': 'text/event-stream; charset=utf-8',
                    'X-Accel-Buffering': 'no',
                },
                _NO_STORE,
            ),
        )

        current_revision, current_text = self._loot_stream.snapshot()
        if current_text:
            writer.write(sse_event(event='loot', data=current_text, event_id=current_revision))
        else:
            writer.write(sse_event(event='empty', data='{}', event_id=current_revision))
        await writer.drain()

        last_revision = current_revision
        while True:
            waiter = self._loot_stream.waiter()
            waited_ms = 0
            while not waiter.is_set() and waited_ms < _LOOT_STREAM_HEARTBEAT_MS:
                await sleep_ms(_LOOT_STREAM_STEP_MS)
                waited_ms += _LOOT_STREAM_STEP_MS

            current_revision, current_text = self._loot_stream.snapshot()
            if current_revision != last_revision:
                if current_text:
                    writer.write(
                        sse_event(event='loot', data=current_text, event_id=current_revision)
                    )
                else:
                    writer.write(sse_event(event='empty', data='{}', event_id=current_revision))
                await writer.drain()
                last_revision = current_revision
                continue

            writer.write(sse_comment('keepalive'))
            await writer.drain()
