import gc
import json
import os

from helpers import sleep_ms
from status_led import STATUS_LED

from .._http import _JSON_HEADERS, _LOOT_FILE, _NO_STORE, _merge_headers, _ticks_ms
from ..execution_stream import ExecutionStreamState
from ..loot_crypto import decrypt, derive_key, encrypt
from ..sse import sse_comment, sse_event

_EXECUTION_STREAM_HEARTBEAT_MS = 15_000
_EXECUTION_STREAM_STEP_MS = 250
_USB_LOOT_FILE = 'loot-usb.json'


class _LootMixin:
    # Attributes provided by SetupServer.__init__
    _execution_stream: ExecutionStreamState
    _ap_password_in_use: str

    # Methods provided by SetupServer
    async def _send(self, writer, request, status: str, body, headers=None) -> None: ...
    async def _send_headers(self, writer, request, status: str, headers=None) -> None: ...
    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None: ...

    def _loot_key(self) -> bytes:
        from device_config import AP_SSID  # type: ignore[import]

        return derive_key(AP_SSID, self._ap_password_in_use)

    def _normalize_loot_record(self, data) -> dict[str, object]:
        record = dict(data) if isinstance(data, dict) else {'payload': data}
        record['timestamp'] = _ticks_ms()
        return record

    def _serialize_loot_record(self, record: dict[str, object]) -> str:
        return json.dumps(record)

    def _read_loot_text(self) -> str:
        with open(_LOOT_FILE, 'rb') as f:
            raw = f.read()
        return decrypt(raw, self._loot_key())

    def _save_loot_data(self, data, *, source: str) -> dict[str, object]:
        record = self._normalize_loot_record(data)
        record['source'] = source
        text = self._serialize_loot_record(record)
        gc.collect()
        with open(_LOOT_FILE, 'wb') as f:
            f.write(encrypt(text, self._loot_key()))
        return record

    def _init_execution_loot(self, target_os: str) -> None:
        """Write a skeleton loot.json when injection begins (HID connection established)."""
        record: dict[str, object] = {
            'execution_step': 'Detect',
            'execution_state': 'success',
            'execution_failure_reason': None,
            'target_os': target_os,
            'timestamp': _ticks_ms(),
            'source': 'binary:usb',
        }
        text = json.dumps(record)
        try:
            with open(_LOOT_FILE, 'wb') as f:
                f.write(encrypt(text, self._loot_key()))
        except (OSError, MemoryError):
            pass

    async def _handle_loot_receive(self, request, writer) -> None:
        gc.collect()
        try:
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
        except ValueError:
            await self._send_json(writer, request, '400 Bad Request', {'message': 'Invalid JSON.'})
            return
        try:
            record = self._save_loot_data(data, source='network')
        except (OSError, MemoryError):
            await self._send_json(
                writer, request, '500 Internal Server Error', {'message': 'Write failed.'}
            )
            return
        self._execution_stream.on_loot_received()
        await self._send_json(
            writer,
            request,
            '200 OK',
            {'message': 'Loot saved.', 'timestamp': record['timestamp']},
        )

    async def _handle_usb_loot_import(self, request, writer) -> None:
        gc.collect()
        try:
            with open(_USB_LOOT_FILE) as f:
                raw = f.read()
        except OSError:
            await self._send_json(
                writer,
                request,
                '404 Not Found',
                {'message': 'No USB loot file found.', 'notice': 'error'},
            )
            return

        try:
            data = json.loads(raw or '{}')
        except ValueError:
            await self._send_json(
                writer,
                request,
                '400 Bad Request',
                {'message': 'USB loot file is not valid JSON.', 'notice': 'error'},
            )
            return

        try:
            record = self._save_loot_data(data, source='usb_drive')
        except (OSError, MemoryError):
            await self._send_json(
                writer,
                request,
                '500 Internal Server Error',
                {'message': 'USB loot import failed.', 'notice': 'error'},
            )
            return

        try:
            os.remove(_USB_LOOT_FILE)
        except OSError:
            pass

        self._execution_stream.on_loot_received()
        await STATUS_LED.show('loot_imported')

        await self._send_json(
            writer,
            request,
            '200 OK',
            {
                'loot': record,
                'message': 'USB loot imported.',
                'notice': 'success',
                'timestamp': record['timestamp'],
            },
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

    async def _handle_execution_stream(self, request, writer) -> None:
        """Stream binary injection execution-step events over SSE.

        Sends discrete 'execution' events as each step starts or finishes,
        followed by a 'done' event when the run completes or errors out.
        A reconnecting client replays all events from the current session.
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

        sent = 0
        while True:
            events = self._execution_stream.events_from(sent)
            if events:
                for ev in events:
                    writer.write(sse_event(event='execution', data=json.dumps(ev)))
                sent += len(events)
                await writer.drain()

            if self._execution_stream.is_complete() and not self._execution_stream.events_from(
                sent
            ):
                writer.write(sse_event(event='done', data='{}'))
                await writer.drain()
                return

            waiter = self._execution_stream.waiter()
            waited = 0
            while not waiter.is_set() and waited < _EXECUTION_STREAM_HEARTBEAT_MS:
                await sleep_ms(_EXECUTION_STREAM_STEP_MS)
                waited += _EXECUTION_STREAM_STEP_MS

            if not self._execution_stream.events_from(sent):
                writer.write(sse_comment('keepalive'))
                await writer.drain()
