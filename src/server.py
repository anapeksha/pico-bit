import asyncio
import binascii
import json
import os

import network

from device_config import (
    ALLOW_UNSAFE,
    AP_PASSWORD,
    AP_SSID,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOWED_ORIGIN,
    PORTAL_AUTH_ENABLED,
    PORTAL_PASSWORD,
    PORTAL_USERNAME,
)
from ducky import (
    DEFAULT_PAYLOAD,
    PAYLOAD_FILE,
    DuckyScriptError,
    ensure_payload,
    find_payload,
    run_script,
    validate_script,
)
from helpers import maybe_wait_closed, sleep_ms
from status_led import STATUS_LED
from web_assets import INDEX_HTML, LOGIN_HTML, PORTAL_CSS, PORTAL_JS

PORT: int = 80
_USB_ENUM_TIMEOUT_MS = 5000
_DEFAULT_AP_IP = '192.168.4.1'
_SESSION_COOKIE = 'pico_bit_session'
_JSON_HEADERS = {'Content-Type': 'application/json; charset=utf-8'}
_NO_STORE = {'Cache-Control': 'no-store'}
_STATIC_CACHE = {'Cache-Control': 'public, max-age=86400'}

__all__ = ['SetupServer', 'SERVER', 'start']


def _esc(s: str) -> str:
    return (
        s.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _urldecode(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == '%' and i + 2 < len(s):
            out.append(chr(int(s[i + 1 : i + 3], 16)))
            i += 3
        elif s[i] == '+':
            out.append(' ')
            i += 1
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


def _parse_form(body: bytes) -> dict[str, str]:
    params: dict[str, str] = {}
    for pair in body.decode('utf-8', 'ignore').split('&'):
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        params[_urldecode(key)] = _urldecode(value)
    return params


def _parse_cookies(header_value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in header_value.split(';'):
        if '=' not in item:
            continue
        key, value = item.split('=', 1)
        cookies[key.strip()] = value.strip()
    return cookies


def _merge_headers(*items) -> dict[str, str]:
    merged: dict[str, str] = {}
    for item in items:
        if not item:
            continue
        for key, value in item.items():
            merged[key] = value
    return merged


async def _read_request(reader):
    request_line = await reader.readline()
    if not request_line:
        return None

    parts = request_line.decode('utf-8', 'ignore').strip().split()
    if len(parts) < 2:
        raise ValueError('malformed request line')

    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if not line or line in (b'\r\n', b'\n'):
            break
        header = line.decode('utf-8', 'ignore').strip()
        if ':' not in header:
            continue
        key, value = header.split(':', 1)
        headers[key.lower()] = value.strip()

    content_length = int(headers.get('content-length', '0') or 0)
    body = b''
    if content_length:
        body = await reader.readexactly(content_length)

    target = parts[1]
    path = target.split('?', 1)[0]
    return {
        'method': parts[0].upper(),
        'path': path,
        'target': target,
        'headers': headers,
        'body': body,
        'cookies': _parse_cookies(headers.get('cookie', '')),
    }


class SetupServer:
    def __init__(self, port: int = PORT) -> None:
        self.port = port
        self._ap = None
        self._ap_ip = _DEFAULT_AP_IP
        self._allow_unsafe = bool(ALLOW_UNSAFE)
        self._kbd = None
        self._ap_password_in_use = AP_PASSWORD
        self._payload_seeded = False
        self._run_lock = None
        self._server = None
        self._sessions: dict[str, str] = {}

    def _seed_payload(self) -> str:
        payload_path, created = ensure_payload(seed=DEFAULT_PAYLOAD)
        if created:
            self._payload_seeded = True
        return payload_path

    def _read_payload(self) -> str:
        payload_path = self._seed_payload()
        try:
            with open(payload_path) as f:
                return f.read()
        except OSError:
            return DEFAULT_PAYLOAD

    def _write_payload(self, content: str) -> str:
        payload_path = find_payload() or PAYLOAD_FILE
        with open(payload_path, 'w') as f:
            f.write(content)
        self._payload_seeded = False
        return payload_path

    def _safe_mode_enabled(self) -> bool:
        return not self._allow_unsafe

    def _set_safe_mode(self, enabled: bool) -> None:
        self._allow_unsafe = not enabled

    def _mode_strings(self) -> tuple[str, str, str]:
        if self._allow_unsafe:
            return (
                'Unsafe mode allowed',
                'Unsafe runtime enabled',
                'Unsafe runtime features are allowed, so advanced commands may execute.',
            )
        return (
            'Safe mode',
            'Unsafe runtime blocked',
            'Safe mode is active, so higher-risk runtime features stay blocked.',
        )

    def _auth_enabled(self) -> bool:
        return PORTAL_AUTH_ENABLED and bool(PORTAL_PASSWORD)

    def _render_login(self, message: str = '', username: str = '') -> str:
        message_class = 'notice--hidden'
        if message:
            message_class = 'notice--error'
        page = LOGIN_HTML
        page = page.replace('{{ap_ssid}}', _esc(AP_SSID))
        page = page.replace('{{message_class}}', message_class)
        page = page.replace('{{message}}', _esc(message))
        page = page.replace('{{username}}', _esc(username))
        return page

    def _keyboard_ready(self) -> bool:
        return self._kbd is not None and self._kbd.is_open()

    def _bootstrap_state(self) -> dict[str, object]:
        mode_label, mode_short, mode_description = self._mode_strings()
        message = ''
        notice = 'quiet'
        if self._payload_seeded:
            message = 'payload.dd was seeded on this boot.'

        return {
            'ap_ip': self._ap_ip,
            'ap_password': self._ap_password_in_use or 'Open network',
            'ap_ssid': AP_SSID,
            'auth_enabled': self._auth_enabled(),
            'keyboard_ready': self._keyboard_ready(),
            'message': message,
            'mode_description': mode_description,
            'mode_label': mode_label,
            'mode_short': mode_short,
            'notice': notice,
            'allow_unsafe': self._allow_unsafe,
            'payload': self._read_payload(),
            'safe_mode_enabled': self._safe_mode_enabled(),
            'seeded': self._payload_seeded,
        }

    def _is_authorized(self, request) -> bool:
        if not self._auth_enabled():
            return True
        token = request['cookies'].get(_SESSION_COOKIE, '')
        return token in self._sessions

    def _new_session(self) -> str:
        token = binascii.hexlify(os.urandom(16)).decode()
        self._sessions[token] = PORTAL_USERNAME
        return token

    def _clear_session(self, request) -> None:
        token = request['cookies'].get(_SESSION_COOKIE, '')
        if token:
            self._sessions.pop(token, None)

    def _session_cookie(self, token: str) -> str:
        return f'{_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict'

    def _expired_session_cookie(self) -> str:
        return f'{_SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict'

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

        writer.write('\r\n'.join(header_lines).encode() + body)
        await writer.drain()

    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None:
        await self._send(
            writer,
            request,
            status,
            json.dumps(data),
            headers=_merge_headers(_JSON_HEADERS, _NO_STORE),
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

    async def execute_script(self, script: str, allow_unsafe: bool | None = None) -> None:
        if allow_unsafe is None:
            allow_unsafe = self._allow_unsafe
        async with self._run_lock_obj():
            validate_script(script)
            keyboard = await self._ensure_keyboard()
            await run_script(keyboard, script, allow_unsafe=allow_unsafe)

    async def _prepare_server(self) -> None:
        if self._server is not None:
            return

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

    async def _run_payload(self, script: str) -> tuple[str, str]:
        try:
            await self.execute_script(script)
            return 'Payload executed.', 'success'
        except DuckyScriptError as exc:
            return f'Error: {exc}', 'error'
        except OSError as exc:
            return f'USB error: {exc}', 'error'

    async def _handle_login(self, request, writer) -> None:
        if not self._auth_enabled():
            await self._redirect(writer, request, '/')
            return

        if request['method'] == 'GET':
            await self._send(
                writer,
                request,
                '200 OK',
                self._render_login(),
                headers=_merge_headers({'Content-Type': 'text/html; charset=utf-8'}, _NO_STORE),
            )
            return

        if request['method'] != 'POST':
            await self._send(writer, request, '405 Method Not Allowed', '405')
            return

        form = _parse_form(request['body'])
        username = form.get('username', '')
        password = form.get('password', '')
        if username == PORTAL_USERNAME and password == PORTAL_PASSWORD:
            token = self._new_session()
            await self._redirect(
                writer,
                request,
                '/',
                headers=_merge_headers({'Set-Cookie': self._session_cookie(token)}, _NO_STORE),
            )
            return

        await self._send(
            writer,
            request,
            '401 Unauthorized',
            self._render_login('Invalid injector credentials.', username=username),
            headers=_merge_headers({'Content-Type': 'text/html; charset=utf-8'}, _NO_STORE),
        )

    async def _handle_api(self, request, writer) -> None:
        if not self._is_authorized(request):
            await self._send_json(
                writer,
                request,
                '401 Unauthorized',
                {'message': 'Sign in required.'},
            )
            return

        if request['method'] == 'GET' and request['path'] == '/api/bootstrap':
            await self._send_json(writer, request, '200 OK', self._bootstrap_state())
            return

        if request['method'] == 'POST' and request['path'] == '/api/payload':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            payload = data.get('payload', '').replace('\r\n', '\n')
            self._write_payload(payload)
            await self._send_json(
                writer,
                request,
                '200 OK',
                {'message': 'payload.dd saved.', 'notice': 'success'},
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/safe-mode':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            enabled = data.get('enabled')
            if not isinstance(enabled, bool):
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {'message': 'safe mode enabled must be a boolean.', 'notice': 'error'},
                )
                return

            self._set_safe_mode(enabled)
            mode_label, mode_short, mode_description = self._mode_strings()
            await self._send_json(
                writer,
                request,
                '200 OK',
                {
                    'allow_unsafe': self._allow_unsafe,
                    'message': 'Safe mode enabled.' if enabled else 'Safe mode disabled.',
                    'mode_description': mode_description,
                    'mode_label': mode_label,
                    'mode_short': mode_short,
                    'notice': 'success',
                    'safe_mode_enabled': self._safe_mode_enabled(),
                },
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/run':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            payload = str(data.get('payload', self._read_payload())).replace('\r\n', '\n')
            if data.get('save', True):
                self._write_payload(payload)
            message, notice = await self._run_payload(payload)
            status = '200 OK' if notice == 'success' else '400 Bad Request'
            await self._send_json(
                writer,
                request,
                status,
                {'message': message, 'notice': notice},
            )
            return

        await self._send_json(writer, request, '404 Not Found', {'message': 'Not found.'})

    async def _dispatch(self, request, writer) -> None:
        if request['method'] == 'OPTIONS':
            await self._send(writer, request, '204 No Content', '', headers=_NO_STORE)
            return

        if request['path'] == '/assets/portal.css':
            await self._send(
                writer,
                request,
                '200 OK',
                PORTAL_CSS,
                headers=_merge_headers({'Content-Type': 'text/css; charset=utf-8'}, _STATIC_CACHE),
            )
            return

        if request['path'] == '/assets/portal.js':
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

        if request['path'].startswith('/api/'):
            await self._handle_api(request, writer)
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
            request = await _read_request(reader)
            if request is None:
                return
            await self._dispatch(request, writer)
        except (ValueError, json.JSONDecodeError):
            fallback = {'method': 'GET', 'path': '/', 'headers': {}, 'body': b'', 'cookies': {}}
            await self._send_json(
                writer,
                fallback,
                '400 Bad Request',
                {'message': 'Malformed request.'},
            )
        except Exception:
            fallback = {'method': 'GET', 'path': '/', 'headers': {}, 'body': b'', 'cookies': {}}
            await self._send_json(
                writer,
                fallback,
                '500 Internal Server Error',
                {'message': 'Unexpected server error.'},
            )
        finally:
            writer.close()
            await maybe_wait_closed(writer)

    async def start(self) -> None:
        await self._prepare_server()

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
