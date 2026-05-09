import asyncio
import gc

import network

from device_config import (
    AP_PASSWORD,
    AP_SSID,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOWED_ORIGIN,
)
from ducky import DuckyScriptError, run_script, validate_script
from helpers import maybe_wait_closed, sleep_ms
from keyboard_layouts import DEFAULT_LAYOUT_CODE
from status_led import STATUS_LED
from web_assets import INDEX_HTML, PORTAL_CSS, PORTAL_JS

from ._http import (
    _AP_CHECK_INTERVAL_MS,
    _DEFAULT_AP_IP,
    _LOGIN_LOCKOUT_MS,
    _MAX_BINARY_SIZE,
    _MAX_LOGIN_ATTEMPTS,
    _NO_STORE,
    _SESSION_TIMEOUT_MS,
    _STATIC_CACHE,
    _USB_ENUM_TIMEOUT_MS,
    _WDT_TIMEOUT_MS,
    PORT,
    _merge_headers,
    _read_request_headers,
    _ticks_add,
    _ticks_ms,
)
from .routes_auth import _AuthMixin
from .routes_binary import _BinaryMixin
from .routes_loot import _LootMixin
from .routes_payload import _PayloadMixin

__all__ = [
    'SetupServer',
    'SERVER',
    'start',
    '_LOGIN_LOCKOUT_MS',
    '_MAX_BINARY_SIZE',
    '_MAX_LOGIN_ATTEMPTS',
    '_SESSION_TIMEOUT_MS',
    '_USB_ENUM_TIMEOUT_MS',
    '_ticks_add',
    '_ticks_ms',
]


class SetupServer(_AuthMixin, _BinaryMixin, _LootMixin, _PayloadMixin):
    def __init__(self, port: int = PORT) -> None:
        self.port = port
        self._ap = None
        self._ap_ip = _DEFAULT_AP_IP
        self._kbd = None
        self._ap_password_in_use = AP_PASSWORD
        self._keyboard_layout = DEFAULT_LAYOUT_CODE
        self._payload_seeded = False
        self._run_lock = None
        self._run_history: list[dict[str, object]] = []
        self._run_sequence = 0
        self._server = None
        self._sessions: dict[str, str] = {}
        self._session_timestamps: dict[str, int] = {}
        self._login_attempts: int = 0
        self._login_lockout_until: int = 0
        self._wdt = None

    async def _send_headers(self, writer, request, status: str, headers=None) -> None:
        gc.collect()
        response_headers = _merge_headers(
            {'Connection': 'close', 'X-Content-Type-Options': 'nosniff'},
            headers,
            self._cors_headers(request),
        )
        header_lines = [f'HTTP/1.1 {status}']
        for key, value in response_headers.items():
            header_lines.append(f'{key}: {value}')
        header_lines.append('')
        header_lines.append('')
        writer.write('\r\n'.join(header_lines).encode())
        await writer.drain()

    def _keyboard_ready(self) -> bool:
        return self._kbd is not None and self._kbd.is_open()

    def _cors_headers(self, request) -> dict[str, str]:
        if not CORS_ALLOWED_ORIGIN:
            return {}

        origin = request['headers'].get('origin', '')
        if CORS_ALLOWED_ORIGIN != '*' and origin != CORS_ALLOWED_ORIGIN:
            return {}

        headers = {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Origin': CORS_ALLOWED_ORIGIN if CORS_ALLOWED_ORIGIN else origin,
        }
        if CORS_ALLOWED_ORIGIN != '*':
            headers['Vary'] = 'Origin'
        if CORS_ALLOW_CREDENTIALS and CORS_ALLOWED_ORIGIN != '*':
            headers['Access-Control-Allow-Credentials'] = 'true'
        return headers

    async def _send(self, writer, request, status: str, body: str | bytes, headers=None) -> None:
        gc.collect()
        response_headers = _merge_headers(
            {'Connection': 'close', 'X-Content-Type-Options': 'nosniff'},
            headers,
            self._cors_headers(request),
        )
        if isinstance(body, str):
            body = body.encode()
        response_headers['Content-Length'] = str(len(body))

        header_lines = [f'HTTP/1.1 {status}']
        for key, value in response_headers.items():
            header_lines.append(f'{key}: {value}')
        header_lines.append('')
        header_lines.append('')

        writer.write('\r\n'.join(header_lines).encode())
        writer.write(body)
        await writer.drain()

    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None:
        import json

        await self._send(
            writer,
            request,
            status,
            json.dumps(data),
            headers=_merge_headers(
                {'Content-Type': 'application/json; charset=utf-8'},
                _NO_STORE,
            ),
        )

    async def _redirect(self, writer, request, location: str, headers=None) -> None:
        await self._send(
            writer,
            request,
            '303 See Other',
            '',
            headers=_merge_headers({'Location': location}, headers),
        )

    async def _start_ap(self) -> str:
        ap_if = getattr(network, 'AP_IF', getattr(network.WLAN, 'IF_AP', 1))
        ap = network.WLAN(ap_if)
        self._ap = ap

        if AP_PASSWORD.strip():
            ap.config(essid=AP_SSID, password=AP_PASSWORD)
            self._ap_password_in_use = AP_PASSWORD
        else:
            ap.config(essid=AP_SSID)
            self._ap_password_in_use = ''

        ap.active(True)

        for _ in range(50):
            if ap.active():
                break
            if self._wdt is not None:
                self._wdt.feed()
            await sleep_ms(100)
        if not ap.active():
            raise OSError('AP failed to come active within 5 s')

        await sleep_ms(250)

        for _ in range(20):
            try:
                ip = ap.ifconfig()[0]
            except (AttributeError, OSError, TypeError, ValueError):
                ip = ''
            if ip and ip != '0.0.0.0':
                self._ap_ip = ip
                return ip
            if self._wdt is not None:
                self._wdt.feed()
            await sleep_ms(100)

        self._ap_ip = _DEFAULT_AP_IP
        return self._ap_ip

    def _run_lock_obj(self):
        if self._run_lock is None:
            self._run_lock = asyncio.Lock()
        return self._run_lock

    def _keyboard(self):
        if self._kbd is None:
            from hid import HIDKeyboard

            self._kbd = HIDKeyboard()
        return self._kbd

    def keyboard(self):
        return self._keyboard()

    async def _ensure_keyboard(self):
        keyboard = self._keyboard()
        ready = await keyboard.wait_open(_USB_ENUM_TIMEOUT_MS)
        if not ready:
            raise OSError('USB HID did not enumerate within 5 s')
        return keyboard

    async def execute_script(self, script: str) -> None:
        async with self._run_lock_obj():
            validate_script(script)
            keyboard = await self._ensure_keyboard()
            await STATUS_LED.show('payload_running')
            await run_script(keyboard, script, default_layout=self._keyboard_layout)

    async def _prepare_server(self) -> None:
        if self._server is not None:
            return

        self._load_keyboard_layout()
        self._seed_payload()

        await STATUS_LED.show('setup_ap_starting')
        await self._start_ap()
        await STATUS_LED.show('setup_ap_ready')

        try:
            self._server = await asyncio.start_server(
                self._handle_request,
                '0.0.0.0',
                self.port,
                backlog=3,
            )
        except OSError as exc:
            raise RuntimeError('setup server bind failed') from exc

        await STATUS_LED.show('setup_server_ready')
        STATUS_LED.on()

    async def _run_payload(self, script: str, *, source: str = 'portal') -> tuple[str, str]:
        try:
            await self.execute_script(script)
            message, notice = 'Payload executed.', 'success'
        except DuckyScriptError as exc:
            message, notice = f'Error: {exc}', 'error'
        except OSError as exc:
            message, notice = f'USB error: {exc}', 'error'
        self._record_run(script, message, notice, source=source)
        return message, notice

    async def _dispatch(self, request, writer) -> None:
        gc.collect()
        if request['method'] == 'OPTIONS':
            await self._send(writer, request, '204 No Content', '', headers=_NO_STORE)
            return

        if request['path'] in ('/portal.css', '/assets/portal.css'):
            await self._send(
                writer,
                request,
                '200 OK',
                PORTAL_CSS,
                headers=_merge_headers({'Content-Type': 'text/css; charset=utf-8'}, _STATIC_CACHE),
            )
            return

        if request['path'] in ('/portal.js', '/assets/portal.js'):
            await self._send(
                writer,
                request,
                '200 OK',
                PORTAL_JS,
                headers=_merge_headers(
                    {'Content-Type': 'application/javascript; charset=utf-8'},
                    _STATIC_CACHE,
                ),
            )
            return

        if request['path'] == '/login':
            await self._handle_login(request, writer)
            return

        if request['path'] == '/logout':
            self._clear_session(request)
            await self._redirect(
                writer,
                request,
                '/login',
                headers=_merge_headers(
                    {'Set-Cookie': self._expired_session_cookie()},
                    _NO_STORE,
                ),
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/loot':
            await self._handle_loot_receive(request, writer)
            return

        if request['path'].startswith('/api/'):
            await self._handle_api(request, writer)
            return

        if request['method'] == 'GET' and request['path'] == '/static/payload.bin':
            await self._serve_payload(writer, request)
            return

        if not self._is_authorized(request):
            await self._redirect(writer, request, '/login')
            return

        if request['path'] == '/':
            await self._send(
                writer,
                request,
                '200 OK',
                INDEX_HTML,
                headers=_merge_headers({'Content-Type': 'text/html; charset=utf-8'}, _NO_STORE),
            )
            return

        await self._send(writer, request, '404 Not Found', '404', headers=_NO_STORE)

    async def _handle_request(self, reader, writer) -> None:
        try:
            partial = await _read_request_headers(reader)
            if partial is None:
                return
            content_length = int(partial['headers'].get('content-length', '0') or 0)
            if partial['method'] == 'POST' and partial['path'] == '/api/upload_binary':
                await self._handle_binary_upload_stream(reader, writer, partial, content_length)
                return
            body = b''
            if content_length:
                body = await reader.readexactly(content_length)
            partial['body'] = body
            await self._dispatch(partial, writer)
        except ValueError:
            fallback = {'method': 'GET', 'path': '/', 'headers': {}, 'body': b'', 'cookies': {}}
            try:
                await self._send_json(
                    writer,
                    fallback,
                    '400 Bad Request',
                    {'message': 'Malformed request.'},
                )
            except Exception:
                pass
        except Exception:
            fallback = {'method': 'GET', 'path': '/', 'headers': {}, 'body': b'', 'cookies': {}}
            try:
                await self._send_json(
                    writer,
                    fallback,
                    '500 Internal Server Error',
                    {'message': 'Unexpected server error.'},
                )
            except Exception:
                pass
        finally:
            writer.close()
            await maybe_wait_closed(writer)

    async def _restart_tcp_server(self) -> None:
        if self._server is not None:
            try:
                self._server.close()
                await maybe_wait_closed(self._server)
            except Exception:
                pass
            self._server = None
        try:
            self._server = await asyncio.start_server(
                self._handle_request, '0.0.0.0', self.port, backlog=3
            )
        except OSError:
            pass

    async def _ensure_ap_active(self) -> None:
        if self._ap is None:
            return
        try:
            if self._ap.active():
                return
        except Exception:
            return
        try:
            await self._start_ap()
        except Exception:
            return
        await self._restart_tcp_server()

    async def _ap_watchdog(self) -> None:
        while True:
            await sleep_ms(_AP_CHECK_INTERVAL_MS)
            if self._wdt is not None:
                self._wdt.feed()
            try:
                await self._ensure_ap_active()
            except Exception:
                pass

    async def start(self) -> None:
        await self._prepare_server()
        try:
            import machine

            _WDT = getattr(machine, 'WDT', None)
            self._wdt = _WDT(timeout=_WDT_TIMEOUT_MS) if _WDT is not None else None
        except Exception:
            self._wdt = None
        asyncio.create_task(self._ap_watchdog())

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await maybe_wait_closed(self._server)
            self._server = None
        if self._ap is not None:
            try:
                self._ap.active(False)
            except OSError:
                pass
            self._ap = None
        self._sessions = {}


SERVER = SetupServer()


async def start() -> None:
    await SERVER.start()
    if SERVER._server is not None:
        await maybe_wait_closed(SERVER._server)
