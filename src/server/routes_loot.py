import gc
import json

from .constants import _LOOT_FILE
from .micro_server import Response


async def receive_loot(portal, request):
    gc.collect()
    try:
        data = json.loads((request.body or b'').decode('utf-8', 'ignore') or '{}')
    except ValueError:
        return portal._json_response({'message': 'Invalid JSON.'}, 400)
    try:
        gc.collect()
        with open(_LOOT_FILE, 'w') as f:
            f.write(json.dumps(data))
    except (OSError, MemoryError):
        return portal._json_response({'message': 'Write failed.'}, 500)
    return portal._json_response({'message': 'Loot saved.'})


async def get_loot(portal, request):
    try:
        with open(_LOOT_FILE) as f:
            content = f.read()
        return Response(
            content.encode('utf-8'),
            200,
            headers={
                'Content-Type': 'application/json; charset=utf-8',
                'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff',
            },
        )
    except OSError:
        return portal._json_response({'message': 'No loot collected yet.'}, 404)


async def download_loot(portal, request):
    try:
        with open(_LOOT_FILE) as f:
            content = f.read()
        return Response(
            content.encode('utf-8'),
            200,
            headers={
                'Content-Type': 'application/json; charset=utf-8',
                'Content-Disposition': 'attachment; filename="loot.json"',
                'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff',
            },
        )
    except OSError:
        return portal._json_response({'message': 'No loot collected yet.'}, 404)
