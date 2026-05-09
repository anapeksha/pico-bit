import gc
import json

from ._http import _LOOT_FILE


class _LootMixin:
    # Methods provided by SetupServer
    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None: ...

    async def _handle_loot_receive(self, request, writer) -> None:
        gc.collect()
        try:
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
        except ValueError:
            await self._send_json(writer, request, '400 Bad Request', {'message': 'Invalid JSON.'})
            return
        try:
            gc.collect()
            with open(_LOOT_FILE, 'w') as f:
                f.write(json.dumps(data))
        except (OSError, MemoryError):
            await self._send_json(
                writer, request, '500 Internal Server Error', {'message': 'Write failed.'}
            )
            return
        await self._send_json(writer, request, '200 OK', {'message': 'Loot saved.'})
