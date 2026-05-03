import asyncio
import binascii
import gc
import json
import os
import time

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
    analyze_script,
    ensure_payload,
    find_payload,
    run_script,
    validate_script,
)
from ducky.analysis import AnalysisResult
from helpers import maybe_wait_closed, sleep_ms
from keyboard_layouts import (
    DEFAULT_LAYOUT_CODE,
    compose_layout_code,
    default_layout_code,
    is_supported_layout,
    is_supported_platform,
    layout_option,
    normalize_layout_code,
    normalize_platform_code,
    split_layout_code,
    supported_layouts,
    supported_platforms,
)
from status_led import STATUS_LED
from web_assets import INDEX_HTML, LOGIN_HTML, PORTAL_CSS, PORTAL_JS

PORT: int = 80
_USB_ENUM_TIMEOUT_MS = 5000
_DEFAULT_AP_IP = '192.168.4.1'
_KEYBOARD_LAYOUT_FILE = 'keyboard_layout.txt'
_RUN_HISTORY_LIMIT = 12
_SESSION_COOKIE = 'pico_bit_session'
_SESSION_TIMEOUT_MS = 30 * 60 * 1000
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_LOCKOUT_MS = 60_000
_AP_CHECK_INTERVAL_MS = 6_000
_WDT_TIMEOUT_MS = 8_000
_PAYLOADS_DIR = 'payloads'
_PAYLOAD_NAME_MAX = 32
_JSON_HEADERS = {'Content-Type': 'application/json; charset=utf-8'}
_NO_STORE = {'Cache-Control': 'no-store'}
_STATIC_CACHE = {'Cache-Control': 'public, max-age=86400'}

__all__ = ['SetupServer', 'SERVER', 'start']


def _esc(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


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


def _ticks_ms() -> int:
    ticks_ms = getattr(time, 'ticks_ms', None)
    if callable(ticks_ms):
        return int(ticks_ms())  # type: ignore
    return int(time.monotonic() * 1000)


def _ticks_add(t: int, delta: int) -> int:
    fn = getattr(time, 'ticks_add', None)
    if callable(fn):
        return int(fn(t, delta))  # type: ignore
    return t + delta


def _ticks_diff(end: int, start: int) -> int:
    fn = getattr(time, 'ticks_diff', None)
    if callable(fn):
        return int(fn(end, start))  # type: ignore
    return end - start


def _validate_payload_name(name: str) -> bool:
    if not name or len(name) > _PAYLOAD_NAME_MAX:
        return False
    return all(c.isalnum() or c in '-_' for c in name)


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

    def _seed_payload(self) -> str:
        payload_path, created = ensure_payload(seed=DEFAULT_PAYLOAD)
        if created:
            self._payload_seeded = True
        return payload_path

    def _read_payload(self) -> str:
        gc.collect()
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

    def _ensure_payloads_dir(self) -> None:
        try:
            os.mkdir(_PAYLOADS_DIR)
        except OSError as exc:
            if exc.args[0] != 17:  # EEXIST
                raise

    def _list_payloads(self) -> list[dict[str, object]]:
        gc.collect()
        try:
            entries = os.listdir(_PAYLOADS_DIR)
        except OSError:
            return []
        result: list[dict[str, object]] = []
        for entry in entries:
            if not entry.endswith('.dd'):
                continue
            name = entry[:-3]
            try:
                size = os.stat(f'{_PAYLOADS_DIR}/{entry}')[6]
            except OSError:
                size = 0
            result.append({'name': name, 'size': size})
        return result

    def _read_named_payload(self, name: str) -> str:
        gc.collect()
        with open(f'{_PAYLOADS_DIR}/{name}.dd') as f:
            return f.read()

    def _write_named_payload(self, name: str, content: str) -> None:
        self._ensure_payloads_dir()
        gc.collect()
        with open(f'{_PAYLOADS_DIR}/{name}.dd', 'w') as f:
            f.write(content)

    def _delete_named_payload(self, name: str) -> None:
        os.remove(f'{_PAYLOADS_DIR}/{name}.dd')

    def _safe_mode_enabled(self) -> bool:
        return not self._allow_unsafe

    def _set_safe_mode(self, enabled: bool) -> None:
        self._allow_unsafe = not enabled

    def _load_keyboard_layout(self) -> str:
        try:
            with open(_KEYBOARD_LAYOUT_FILE) as f:
                raw = f.read().strip()
        except OSError:
            raw = ''

        normalized = normalize_layout_code(raw or self._keyboard_layout)
        if normalized not in {item['code'] for item in supported_layouts()}:
            normalized = DEFAULT_LAYOUT_CODE
        self._keyboard_layout = normalized
        return self._keyboard_layout

    def _persist_keyboard_layout(self, code: str) -> None:
        with open(_KEYBOARD_LAYOUT_FILE, 'w') as f:
            f.write(code + '\n')

    def _set_keyboard_layout(self, code: str, *, persist: bool = False) -> str:
        normalized = normalize_layout_code(code)
        if not is_supported_layout(normalized):
            raise ValueError('unsupported keyboard layout')
        self._keyboard_layout = normalized
        if persist:
            self._persist_keyboard_layout(normalized)
        return normalized

    def _keyboard_layout_state(self) -> dict[str, object]:
        option = layout_option(self._keyboard_layout)
        platform, layout = split_layout_code(self._keyboard_layout)
        target_label = option['platform_label'] + ' · ' + option['label']
        return {
            'keyboard_layout': layout,
            'keyboard_layout_code': layout,
            'keyboard_layout_hint': 'Used for typed text and remembered on the device.',
            'keyboard_layout_label': option['label'],
            'keyboard_layout_platform': option['platform'],
            'keyboard_layout_profile': option['code'],
            'keyboard_layout_profile_code': option['code'],
            'keyboard_layout_short': option['layout'],
            'keyboard_layouts': supported_layouts(platform),
            'keyboard_os': platform,
            'keyboard_os_code': platform,
            'keyboard_os_label': option['platform_label'],
            'keyboard_oses': supported_platforms(),
            'keyboard_target_label': target_label,
        }

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

    def _validation_state(self, script: str) -> AnalysisResult:
        return analyze_script(script, allow_unsafe=self._allow_unsafe)

    def _history_preview(self, script: str) -> str:
        for raw_line in script.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            stripped = raw_line.strip()
            upper = stripped.upper()
            if not stripped or upper == 'REM' or upper.startswith('REM ') or upper.startswith('//'):
                continue
            if len(stripped) > 72:
                return stripped[:69] + '...'
            return stripped
        return 'Empty payload'

    def _recent_runs(self) -> list[dict[str, object]]:
        return [dict(item) for item in self._run_history]

    def _record_run(self, script: str, message: str, notice: str, *, source: str) -> None:
        self._run_sequence += 1
        mode_label, _mode_short, _mode_description = self._mode_strings()
        self._run_history.insert(
            0,
            {
                'at_ms': _ticks_ms(),
                'message': message,
                'mode_label': mode_label,
                'notice': notice,
                'preview': self._history_preview(script),
                'safe_mode_enabled': self._safe_mode_enabled(),
                'sequence': self._run_sequence,
                'source': source,
            },
        )
        del self._run_history[_RUN_HISTORY_LIMIT:]

    def record_run(self, script: str, message: str, notice: str, *, source: str) -> None:
        self._record_run(script, message, notice, source=source)

    def _auth_enabled(self) -> bool:
        return PORTAL_AUTH_ENABLED and bool(PORTAL_PASSWORD)

    def _render_login(self, message: str = '', username: str = '') -> str:
        message_class = 'notice--hidden'
        if message:
            message_class = 'notice--error'
        page = LOGIN_HTML.decode()
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
        payload = self._read_payload()

        state = {
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
            'payload': payload,
            'run_history': self._recent_runs(),
            'safe_mode_enabled': self._safe_mode_enabled(),
            'seeded': self._payload_seeded,
        }
        state.update(self._keyboard_layout_state())
        return state

    def _is_authorized(self, request) -> bool:
        if not self._auth_enabled():
            return True
        token = request['cookies'].get(_SESSION_COOKIE, '')
        if token not in self._sessions:
            return False
        last = self._session_timestamps.get(token, _ticks_ms())
        if _ticks_diff(_ticks_ms(), last) > _SESSION_TIMEOUT_MS:
            self._sessions.pop(token, None)
            self._session_timestamps.pop(token, None)
            return False
        self._session_timestamps[token] = _ticks_ms()
        return True

    def _new_session(self) -> str:
        token = binascii.hexlify(os.urandom(16)).decode()
        self._sessions[token] = PORTAL_USERNAME
        self._session_timestamps[token] = _ticks_ms()
        return token

    def _clear_session(self, request) -> None:
        token = request['cookies'].get(_SESSION_COOKIE, '')
        if token:
            self._sessions.pop(token, None)
            self._session_timestamps.pop(token, None)

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

    async def execute_script(self, script: str, allow_unsafe: bool | None = None) -> None:
        if allow_unsafe is None:
            allow_unsafe = self._allow_unsafe
        async with self._run_lock_obj():
            validate_script(script)
            keyboard = await self._ensure_keyboard()
            await STATUS_LED.show('payload_running')
            await run_script(
                keyboard,
                script,
                allow_unsafe=allow_unsafe,
                default_layout=self._keyboard_layout,
            )

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

    def _lockout_remaining_s(self) -> int:
        if not self._login_lockout_until:
            return 0
        remaining = _ticks_diff(self._login_lockout_until, _ticks_ms())
        if remaining <= 0:
            self._login_lockout_until = 0
            return 0
        return remaining // 1000 + 1

    async def _handle_login(self, request, writer) -> None:
        if not self._auth_enabled():
            await self._redirect(writer, request, '/')
            return

        remaining_s = self._lockout_remaining_s()

        if request['method'] == 'GET':
            message = f'Too many attempts. Try again in {remaining_s}s.' if remaining_s else ''
            await self._send(
                writer,
                request,
                '200 OK',
                self._render_login(message),
                headers=_merge_headers({'Content-Type': 'text/html; charset=utf-8'}, _NO_STORE),
            )
            return

        if request['method'] != 'POST':
            await self._send(writer, request, '405 Method Not Allowed', '405')
            return

        if remaining_s:
            await self._send(
                writer,
                request,
                '429 Too Many Requests',
                self._render_login(f'Too many attempts. Try again in {remaining_s}s.'),
                headers=_merge_headers({'Content-Type': 'text/html; charset=utf-8'}, _NO_STORE),
            )
            return

        form = _parse_form(request['body'])
        username = form.get('username', '')
        password = form.get('password', '')
        if username == PORTAL_USERNAME and password == PORTAL_PASSWORD:
            self._login_attempts = 0
            self._login_lockout_until = 0
            token = self._new_session()
            await self._redirect(
                writer,
                request,
                '/',
                headers=_merge_headers({'Set-Cookie': self._session_cookie(token)}, _NO_STORE),
            )
            return

        self._login_attempts += 1
        if self._login_attempts >= _MAX_LOGIN_ATTEMPTS:
            self._login_lockout_until = _ticks_add(_ticks_ms(), _LOGIN_LOCKOUT_MS)
            self._login_attempts = 0
            remaining_s = _LOGIN_LOCKOUT_MS // 1000
        await self._send(
            writer,
            request,
            '401 Unauthorized',
            self._render_login(
                f'Too many attempts. Try again in {remaining_s}s.'
                if remaining_s
                else 'Invalid injector credentials.',
                username=username,
            ),
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
            payload = str(data.get('payload', '')).replace('\r\n', '\n')
            validation = self._validation_state(payload)
            if validation['blocking']:
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {
                        'message': validation['summary'],
                        'notice': 'error',
                        'validation': validation,
                    },
                )
                return

            self._write_payload(payload)
            await self._send_json(
                writer,
                request,
                '200 OK',
                {
                    'message': 'payload.dd saved.',
                    'notice': 'success',
                    'validation': validation,
                },
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/validate':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            payload = str(data.get('payload', '')).replace('\r\n', '\n')
            validation = self._validation_state(payload)
            await self._send_json(
                writer,
                request,
                '200 OK',
                {
                    'message': validation['summary'],
                    'notice': validation['notice'],
                    'validation': validation,
                },
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
            await STATUS_LED.show('safe_mode_changed')
            mode_label, mode_short, mode_description = self._mode_strings()
            payload = data.get('payload')
            validation = None
            if isinstance(payload, str):
                validation = self._validation_state(payload.replace('\r\n', '\n'))
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
                    'validation': validation,
                },
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/keyboard-layout':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            requested_os = data.get('os')
            requested_layout = data.get('layout')
            current_os, _current_layout = split_layout_code(self._keyboard_layout)

            if requested_os is not None and not is_supported_platform(str(requested_os)):
                response_payload: dict[str, object] = {
                    'message': 'Unsupported operating system.',
                    'notice': 'error',
                }
                response_payload.update(self._keyboard_layout_state())
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    response_payload,
                )
                return

            platform = normalize_platform_code(str(requested_os or current_os))
            layout_text = str(requested_layout or '').strip()
            if layout_text:
                normalized = compose_layout_code(platform, layout_text)
                if not is_supported_layout(normalized):
                    platform_label = layout_option(default_layout_code(platform))['platform_label']
                    response_payload: dict[str, object] = {
                        'message': f'Unsupported keyboard layout for {platform_label}.',
                        'notice': 'error',
                    }
                    response_payload.update(self._keyboard_layout_state())
                    await self._send_json(
                        writer,
                        request,
                        '400 Bad Request',
                        response_payload,
                    )
                    return
            else:
                normalized = default_layout_code(platform)

            self._set_keyboard_layout(normalized, persist=True)
            await STATUS_LED.show('keyboard_layout_changed')
            option = layout_option(normalized)
            response_payload: dict[str, object] = {
                'message': f'Typing target set to {option["platform_label"]} · {option["label"]}.',
                'notice': 'success',
            }
            response_payload.update(self._keyboard_layout_state())
            await self._send_json(
                writer,
                request,
                '200 OK',
                response_payload,
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/run':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            payload = str(data.get('payload', self._read_payload())).replace('\r\n', '\n')
            validation = self._validation_state(payload)
            if validation['blocking']:
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {
                        'message': validation['summary'],
                        'notice': 'error',
                        'validation': validation,
                    },
                )
                return

            if data.get('save', True):
                self._write_payload(payload)
            message, notice = await self._run_payload(payload)
            status = '200 OK' if notice == 'success' else '400 Bad Request'
            await self._send_json(
                writer,
                request,
                status,
                {
                    'message': message,
                    'notice': notice,
                    'run_history': self._recent_runs(),
                    'validation': validation,
                },
            )
            return

        path = request['path']
        method = request['method']

        if path == '/api/payloads' and method == 'GET':
            await self._send_json(writer, request, '200 OK', {'payloads': self._list_payloads()})
            return

        if path == '/api/payloads' and method == 'POST':
            gc.collect()
            try:
                data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            except ValueError:
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {'message': 'Invalid JSON body.', 'notice': 'error'},
                )
                return
            name = str(data.get('name', '')).strip()
            if not _validate_payload_name(name):
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {
                        'message': 'Name must be 1-32 alphanumeric, hyphen, or underscore chars.',
                        'notice': 'error',
                    },
                )
                return
            content = str(data.get('payload', '')).replace('\r\n', '\n')
            try:
                self._write_named_payload(name, content)
            except OSError as exc:
                errno_code = exc.args[0] if exc.args else 0
                if errno_code == 28:  # ENOSPC
                    msg = 'No space left on device.'
                elif errno_code == 30:  # EROFS
                    msg = 'Filesystem is read-only.'
                elif errno_code == 2:  # ENOENT — payloads dir missing
                    msg = 'Could not create payloads directory.'
                else:
                    msg = f'Write failed (errno {errno_code}).'
                await self._send_json(
                    writer,
                    request,
                    '500 Internal Server Error',
                    {'message': msg, 'notice': 'error'},
                )
                return
            except MemoryError:
                await self._send_json(
                    writer,
                    request,
                    '500 Internal Server Error',
                    {
                        'message': 'Not enough memory to save payload. Try a shorter payload.',
                        'notice': 'error',
                    },
                )
                return
            except Exception:
                await self._send_json(
                    writer,
                    request,
                    '500 Internal Server Error',
                    {'message': 'Save failed.', 'notice': 'error'},
                )
                return
            await self._send_json(
                writer,
                request,
                '200 OK',
                {'message': f'Saved as {name}.dd', 'notice': 'success', 'name': name},
            )
            return

        if path.startswith('/api/payloads/'):
            rest = path[len('/api/payloads/') :]
            if '/' in rest:
                pname, action = rest.split('/', 1)
            else:
                pname, action = rest, ''

            if not _validate_payload_name(pname):
                await self._send_json(
                    writer, request, '400 Bad Request', {'message': 'Invalid payload name.'}
                )
                return

            if not action and method == 'GET':
                gc.collect()
                try:
                    content = self._read_named_payload(pname)
                except OSError:
                    await self._send_json(
                        writer, request, '404 Not Found', {'message': 'Payload not found.'}
                    )
                    return
                await self._send_json(
                    writer, request, '200 OK', {'name': pname, 'payload': content}
                )
                return

            if not action and method == 'DELETE':
                try:
                    self._delete_named_payload(pname)
                except OSError:
                    await self._send_json(
                        writer, request, '404 Not Found', {'message': 'Payload not found.'}
                    )
                    return
                await self._send_json(
                    writer,
                    request,
                    '200 OK',
                    {'message': f'Deleted {pname}.dd', 'notice': 'success'},
                )
                return

            await self._send_json(
                writer, request, '405 Method Not Allowed', {'message': 'Method not allowed.'}
            )
            return

        await self._send_json(writer, request, '404 Not Found', {'message': 'Not found.'})

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
