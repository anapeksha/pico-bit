import asyncio  # noqa: F401  — kept for monkeypatch.setattr(server.asyncio, ...) in tests

import network

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
)
from .micro_server import MicroServer, Request, Response, SessionAuth
from .service import _Service


def _secure_compare(a, b):
    if len(a) != len(b):
        return False
    result = 0
    for ca, cb in zip(a, b):  # noqa: B905
        result |= ord(ca) ^ ord(cb)
    return result == 0


__all__ = ['SetupServer', 'SERVER', 'start']

Request.max_content_length = _MAX_BINARY_SIZE


class SetupServer(_Service):
    def __init__(self, port=PORT):
        self.port = port
        self.app = MicroServer()
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
        self._wdt = None
        self.auth = SessionAuth(
            cookie_name=_SESSION_COOKIE,
            timeout_ms=_SESSION_TIMEOUT_MS,
            max_attempts=_MAX_LOGIN_ATTEMPTS,
            lockout_ms=_LOGIN_LOCKOUT_MS,
            enabled_fn=lambda: PORTAL_AUTH_ENABLED and bool(PORTAL_PASSWORD),
        )

        @self.auth.authenticate
        def _verify(username, password):
            return _secure_compare(username, PORTAL_USERNAME) and _secure_compare(
                password, PORTAL_PASSWORD
            )

        self._register_routes()

    # ── Login handler ────────────────────────────────────────────────────────

    async def _handle_login(self, request):
        if not self.auth.enabled:
            return Response(b'', 303, headers={'Location': '/'})

        remaining_s = self.auth.lockout_remaining_s()

        if request.method == 'GET':
            msg = f'Too many attempts. Try again in {remaining_s}s.' if remaining_s else ''
            return Response(
                self._render_login(msg).encode('utf-8'),
                200,
                headers={
                    'Content-Type': 'text/html; charset=utf-8',
                    'Cache-Control': 'no-store',
                    'X-Content-Type-Options': 'nosniff',
                },
            )

        if remaining_s:
            return Response(
                self._render_login(f'Too many attempts. Try again in {remaining_s}s.').encode(
                    'utf-8'
                ),
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
        if await self.auth.verify(username, password):
            self.auth.reset_attempts()
            token = self.auth.login(username)
            return Response(
                b'',
                303,
                headers={  # type: ignore[arg-type]
                    'Location': '/',
                    'Set-Cookie': [self.auth.session_cookie(token)],
                    'Cache-Control': 'no-store',
                },
            )

        lockout_s = self.auth.record_failed_attempt()
        if lockout_s:
            remaining_s = lockout_s
        return Response(
            self._render_login(
                f'Too many attempts. Try again in {remaining_s}s.'
                if remaining_s
                else 'Invalid injector credentials.',
                username=username,
            ).encode('utf-8'),
            401,
            headers={
                'Content-Type': 'text/html; charset=utf-8',
                'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff',
            },
        )

    # ── AP ───────────────────────────────────────────────────────────────────

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

    # ── HID execution ────────────────────────────────────────────────────────

    async def execute_script(self, script):
        async with self._run_lock_obj():
            validate_script(script)
            keyboard = await self._ensure_keyboard()
            await STATUS_LED.show('payload_running')
            await run_script(keyboard, script, default_layout=self._keyboard_layout)

    # ── Route registration ───────────────────────────────────────────────────

    def _register_routes(self):
        app = self.app
        auth = self.auth

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
        async def _add_headers(request, response):
            cors = self._cors_headers(request)
            for key, value in cors.items():
                response.headers[key] = value
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "frame-ancestors 'none'"
            )
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
        @auth.api
        async def _upload_binary(request):
            return await upload_binary(self, request)

        @app.get('/api/bootstrap')
        @auth.api
        async def _api_bootstrap_route(request):
            return await api_bootstrap(self, request)

        @app.post('/api/payload')
        @auth.api
        async def _api_payload_route(request):
            return await api_payload(self, request)

        @app.post('/api/validate')
        @auth.api
        async def _api_validate_route(request):
            return await api_validate(self, request)

        @app.post('/api/keyboard-layout')
        @auth.api
        async def _api_keyboard_layout_route(request):
            return await api_keyboard_layout(self, request)

        @app.post('/api/run')
        @auth.api
        async def _api_run_route(request):
            return await api_run(self, request)

        @app.get('/api/loot')
        @auth.api
        async def _api_loot_get_route(request):
            return await get_loot(self, request)

        @app.get('/api/loot/download')
        @auth.api
        async def _api_loot_download_route(request):
            return await download_loot(self, request)

        @app.post('/api/inject_binary')
        @auth.api
        async def _api_inject_binary_route(request):
            return await inject_binary(self, request)

        @app.get('/')
        @auth
        async def _index_route(request):
            return await handle_index(self, request)

        @app.route('/<path:path>', methods=['OPTIONS'])
        async def _options_handler(request, path):
            return Response(b'', 204, headers={'Cache-Control': 'no-store'})


SERVER = SetupServer()


async def start():
    await SERVER.start()
    if SERVER._server is not None:
        await maybe_wait_closed(SERVER._server)
