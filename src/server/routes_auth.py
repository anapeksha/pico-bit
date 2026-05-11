import binascii
import os

from device_config import PORTAL_AUTH_ENABLED, PORTAL_PASSWORD, PORTAL_USERNAME
from web_assets import INDEX_HTML

from ._http import (
    _LOGIN_LOCKOUT_MS,
    _MAX_LOGIN_ATTEMPTS,
    _NO_STORE,
    _SESSION_COOKIE,
    _SESSION_TIMEOUT_MS,
    _esc,
    _merge_headers,
    _parse_form,
    _ticks_add,
    _ticks_diff,
    _ticks_ms,
)


class _AuthMixin:
    # Attributes provided by SetupServer.__init__
    _sessions: dict[str, str]
    _session_timestamps: dict[str, int]
    _login_attempts: int
    _login_lockout_until: int

    # Methods provided by SetupServer
    async def _redirect(self, writer, request, location: str, headers=None) -> None: ...
    async def _send(self, writer, request, status: str, body, headers=None) -> None: ...

    def _auth_enabled(self) -> bool:
        return PORTAL_AUTH_ENABLED and bool(PORTAL_PASSWORD)

    def _render_app(self, auth_state: str = 'portal', message: str = '', username: str = '') -> str:
        message_class = 'notice--hidden'
        if message:
            message_class = 'notice--error'
        page = INDEX_HTML.decode()
        page = page.replace('{{auth_state}}', auth_state)
        page = page.replace('{{message_class}}', message_class)
        page = page.replace('{{message}}', _esc(message))
        page = page.replace('{{username}}', _esc(username))
        return page

    def _render_login(self, message: str = '', username: str = '') -> str:
        return self._render_app('login', message, username)

    def _render_portal(self) -> str:
        return self._render_app('portal')

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
