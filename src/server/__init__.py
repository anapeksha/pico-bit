import asyncio  # noqa: F401  — kept for monkeypatch.setattr(server.asyncio, ...) in tests
import binascii
import os

import network
from microdot import Microdot
from microdot.microdot import Request, Response

from device_config import (
    AP_PASSWORD,
    AP_SSID,
    PORTAL_AUTH_ENABLED,
    PORTAL_PASSWORD,
    PORTAL_USERNAME,
)
from ducky import run_script, validate_script
from helpers import maybe_wait_closed, sleep_ms
from keyboard_layouts import DEFAULT_LAYOUT_CODE
from status_led import STATUS_LED
from web_assets import PORTAL_CSS, PORTAL_JS

from .constants import (
    _DEFAULT_AP_IP,
    _LOGIN_LOCKOUT_MS,
    _MAX_BINARY_SIZE,
    _MAX_LOGIN_ATTEMPTS,
    _SESSION_COOKIE,
    _SESSION_TIMEOUT_MS,
    _USB_ENUM_TIMEOUT_MS,  # noqa: F401  — read by tests as server._USB_ENUM_TIMEOUT_MS
    PORT,
    _parse_form,
    _ticks_add,
    _ticks_diff,
    _ticks_ms,
)
from .service import _Service

__all__ = ['SetupServer', 'SERVER', 'start']

Request.max_content_length = _MAX_BINARY_SIZE


class SetupServer(_Service):
    def __init__(self, port=PORT):
        self.port = port
        self.app = Microdot()
        self._ap = None
        self._ap_ip = _DEFAULT_AP_IP
        self._kbd = None
        self._ap_password_in_use = AP_PASSWORD
        self._keyboard_layout = DEFAULT_LAYOUT_CODE
        self._payload_seeded = False
        self._run_lock = None
        self._run_history = []
        self._run_sequence = 0
        self._server = None
        self._sessions = {}
        self._session_timestamps = {}
        self._login_attempts = 0
        self._login_lockout_until = 0
        self._wdt = None
        self._register_routes()

    # ── Auth helpers (reference patchable module globals) ────────────────────

    def _auth_enabled(self):
        return PORTAL_AUTH_ENABLED and bool(PORTAL_PASSWORD)

    def _is_authorized(self, request):
        if not self._auth_enabled():
            return True
        token = request.cookies.get(_SESSION_COOKIE, '')
        if token not in self._sessions:
            return False
        last = self._session_timestamps.get(token, _ticks_ms())
        if _ticks_diff(_ticks_ms(), last) > _SESSION_TIMEOUT_MS:
            self._sessions.pop(token, None)
            self._session_timestamps.pop(token, None)
            return False
        self._session_timestamps[token] = _ticks_ms()
        return True

    def _new_session(self):
        token = binascii.hexlify(os.urandom(16)).decode()
        self._sessions[token] = PORTAL_USERNAME
        self._session_timestamps[token] = _ticks_ms()
        return token

    def _lockout_remaining_s(self):
        if not self._login_lockout_until:
            return 0
        remaining = _ticks_diff(self._login_lockout_until, _ticks_ms())
        if remaining <= 0:
            self._login_lockout_until = 0
            return 0
        return remaining // 1000 + 1

    # ── Login handler (references PORTAL_USERNAME, PORTAL_PASSWORD, _ticks_*) ─

    async def _handle_login(self, request):
        if not self._auth_enabled():
            return Response(b'', 303, headers={'Location': '/'})

        remaining_s = self._lockout_remaining_s()

        if request.method == 'GET':
            msg = f'Too many attempts. Try again in {remaining_s}s.' if remaining_s else ''
            return Response(
                self._render_login(msg),
                200,
                headers={
                    'Content-Type': 'text/html; charset=utf-8',
                    'Cache-Control': 'no-store',
                    'X-Content-Type-Options': 'nosniff',
                },
            )

        if remaining_s:
            return Response(
                self._render_login(f'Too many attempts. Try again in {remaining_s}s.'),
                429,
                headers={
                    'Content-Type': 'text/html; charset=utf-8',
                    'Cache-Control': 'no-store',
                    'X-Content-Type-Options': 'nosniff',
                },
            )

        form = _parse_form(request.body or b'')
        username = form.get('username', '')
        password = form.get('password', '')
        if username == PORTAL_USERNAME and password == PORTAL_PASSWORD:
            self._login_attempts = 0
            self._login_lockout_until = 0
            token = self._new_session()
            return Response(
                b'',
                303,
                headers={
                    'Location': '/',
                    'Set-Cookie': self._session_cookie(token),
                    'Cache-Control': 'no-store',
                },
            )

        self._login_attempts += 1
        if self._login_attempts >= _MAX_LOGIN_ATTEMPTS:
            self._login_lockout_until = _ticks_add(_ticks_ms(), _LOGIN_LOCKOUT_MS)
            self._login_attempts = 0
            remaining_s = _LOGIN_LOCKOUT_MS // 1000
        return Response(
            self._render_login(
                f'Too many attempts. Try again in {remaining_s}s.'
                if remaining_s
                else 'Invalid injector credentials.',
                username=username,
            ),
            401,
            headers={
                'Content-Type': 'text/html; charset=utf-8',
                'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff',
            },
        )

    # ── AP (references AP_PASSWORD, AP_SSID, network, sleep_ms) ─────────────

    async def _start_ap(self):
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

    # ── HID execution (references validate_script, run_script, STATUS_LED) ───

    async def execute_script(self, script):
        async with self._run_lock_obj():
            validate_script(script)
            keyboard = await self._ensure_keyboard()
            await STATUS_LED.show('payload_running')
            await run_script(keyboard, script, default_layout=self._keyboard_layout)

    # ── Route registration ───────────────────────────────────────────────────

    def _register_routes(self):
        app = self.app

        from .routes_auth import handle_index, handle_logout
        from .routes_binary import inject_binary, serve_payload, upload_binary
        from .routes_loot import download_loot, get_loot, receive_loot
        from .routes_payload import (
            api_bootstrap,
            api_keyboard_layout,
            api_payload,
            api_run,
            api_validate,
        )

        @app.after_request
        async def _add_cors(request, response):
            cors = self._cors_headers(request)
            for key, value in cors.items():
                response.headers[key] = value
            return response

        @app.route('/portal.css', methods=['GET'])
        @app.route('/assets/portal.css', methods=['GET'])
        async def _serve_css(request):
            return Response(
                PORTAL_CSS,
                200,
                headers={
                    'Content-Type': 'text/css; charset=utf-8',
                    'Cache-Control': 'public, max-age=86400',
                    'X-Content-Type-Options': 'nosniff',
                },
            )

        @app.route('/portal.js', methods=['GET'])
        @app.route('/assets/portal.js', methods=['GET'])
        async def _serve_js(request):
            return Response(
                PORTAL_JS,
                200,
                headers={
                    'Content-Type': 'application/javascript; charset=utf-8',
                    'Cache-Control': 'public, max-age=86400',
                    'X-Content-Type-Options': 'nosniff',
                },
            )

        @app.route('/login', methods=['GET', 'POST'])
        async def _login_route(request):
            return await self._handle_login(request)

        @app.route('/logout', methods=['GET', 'POST'])
        async def _logout_route(request):
            return await handle_logout(self, request)

        @app.post('/api/loot')
        async def _loot_receive(request):
            return await receive_loot(self, request)

        @app.get('/static/payload.bin')
        async def _serve_payload_route(request):
            return await serve_payload(self, request)

        @app.post('/api/upload_binary')
        async def _upload_binary(request):
            return await upload_binary(self, request)

        @app.get('/api/bootstrap')
        async def _api_bootstrap_route(request):
            return await api_bootstrap(self, request)

        @app.post('/api/payload')
        async def _api_payload_route(request):
            return await api_payload(self, request)

        @app.post('/api/validate')
        async def _api_validate_route(request):
            return await api_validate(self, request)

        @app.post('/api/keyboard-layout')
        async def _api_keyboard_layout_route(request):
            return await api_keyboard_layout(self, request)

        @app.post('/api/run')
        async def _api_run_route(request):
            return await api_run(self, request)

        @app.get('/api/loot')
        async def _api_loot_get_route(request):
            return await get_loot(self, request)

        @app.get('/api/loot/download')
        async def _api_loot_download_route(request):
            return await download_loot(self, request)

        @app.post('/api/inject_binary')
        async def _api_inject_binary_route(request):
            return await inject_binary(self, request)

        @app.get('/')
        async def _index_route(request):
            return await handle_index(self, request)

        @app.route('/<path:path>', methods=['OPTIONS'])
        async def _options_handler(request, path):
            return Response(b'', 204, headers={'Cache-Control': 'no-store'})


SERVER = SetupServer()


async def start() -> None:
    await SERVER.start()
    if SERVER._server is not None:
        await maybe_wait_closed(SERVER._server)
