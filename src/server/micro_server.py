import binascii
import io
import json
import os
import re
import time as _time

_ticks_ms = getattr(_time, 'ticks_ms', lambda: int(_time.monotonic() * 1000))
_ticks_diff = getattr(_time, 'ticks_diff', lambda a, b: a - b)
_ticks_add = getattr(_time, 'ticks_add', lambda t, d: t + d)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _re_escape(s):
    special = r'\.^$*+?{}[]|()'
    out = []
    for c in s:
        if c in special:
            out.append('\\')
        out.append(c)
    return ''.join(out)


_STATUS_REASONS = {
    200: 'OK',
    201: 'Created',
    204: 'No Content',
    301: 'Moved Permanently',
    303: 'See Other',
    304: 'Not Modified',
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    429: 'Too Many Requests',
    500: 'Internal Server Error',
}


# ── NoCaseDict ────────────────────────────────────────────────────────────────


class NoCaseDict(dict):
    """Case-insensitive HTTP header dict. Keys are stored and compared lowercase."""

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __contains__(self, key):
        return super().__contains__(key.lower())

    def get(self, key, default=None):
        return super().get(key.lower(), default)


# ── AsyncBytesIO (test helper) ────────────────────────────────────────────────


class AsyncBytesIO:
    """Async-compatible wrapper around BytesIO used by the test client."""

    def __init__(self, data=b''):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self._stream = io.BytesIO(data)

    async def read(self, n=-1):
        return self._stream.read(n)

    async def readexactly(self, n):
        return self._stream.read(n)

    async def readline(self):
        return self._stream.readline()

    def write(self, data):
        self._stream.write(data)

    async def awrite(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self._stream.write(data)

    async def drain(self):
        pass

    async def aclose(self):
        pass

    def getvalue(self):
        return self._stream.getvalue()


# ── URLPattern ────────────────────────────────────────────────────────────────


class URLPattern:
    """Compiles a URL pattern with <name>, <int:name>, <path:name> placeholders."""

    def __init__(self, pattern):
        self._param_names = []
        regex = '^'
        remaining = pattern
        while '<' in remaining:
            idx = remaining.index('<')
            regex += _re_escape(remaining[:idx])
            remaining = remaining[idx + 1 :]
            end = remaining.index('>')
            spec = remaining[:end]
            remaining = remaining[end + 1 :]
            if ':' in spec:
                ptype, pname = spec.split(':', 1)
            else:
                ptype, pname = 'string', spec
            self._param_names.append((pname, ptype))
            if ptype == 'int':
                regex += r'(\d+)'
            elif ptype == 'path':
                regex += r'(.+)'
            else:
                regex += r'([^/]+)'
        self._re = re.compile(regex + _re_escape(remaining) + '$')

    def match(self, path):
        m = self._re.match(path)
        if not m:
            return None
        params = {}
        for i, (name, ptype) in enumerate(self._param_names):
            v = m.group(i + 1)
            params[name] = int(v) if ptype == 'int' else v
        return params


# ── Request ───────────────────────────────────────────────────────────────────


class Request:
    max_content_length = 16 * 1024
    max_body_length = 16 * 1024

    def __init__(
        self,
        app,
        client_addr,
        method,
        url,
        http_version,
        headers,  # noqa: PLR0913
        body=None,
        stream=None,
        sock=None,
        url_prefix='',
        subapp=None,
        scheme=None,
        route=None,
    ):
        self.app = app
        self.client_addr = client_addr
        self.method = method
        self.http_version = http_version
        self.headers = headers
        self.body = body
        self.stream = stream
        self.scheme = scheme
        if '?' in url:
            self.path, self.query_string = url.split('?', 1)
        else:
            self.path, self.query_string = url, ''
        self.cookies = {}
        cookie_hdr = headers.get('cookie', '')
        if cookie_hdr:
            for part in cookie_hdr.split(';'):
                part = part.strip()
                if '=' in part:
                    k, v = part.split('=', 1)
                    self.cookies[k.strip()] = v.strip()

    @property
    def content_length(self):
        return int(self.headers.get('content-length', 0) or 0)

    @staticmethod
    async def create(app, client_reader, client_writer, client_addr, scheme=None):
        line = await client_reader.readline()
        if not line:
            return None
        line = line.decode('utf-8', 'ignore').strip()
        parts = line.split(' ', 2)
        if len(parts) < 2:
            return None
        method = parts[0]
        url = parts[1]
        http_version = parts[2].split('/', 1)[1] if len(parts) == 3 and '/' in parts[2] else '1.0'

        headers = NoCaseDict()
        while True:
            hline = await client_reader.readline()
            if not hline or hline in (b'\r\n', b'\n', b''):
                break
            hline = hline.decode('utf-8', 'ignore').strip()
            if ':' in hline:
                k, v = hline.split(':', 1)
                headers[k.strip()] = v.strip()

        content_length = int(headers.get('content-length', 0) or 0)
        if content_length > Request.max_content_length:
            return None

        body = None
        stream = None
        if 0 < content_length <= Request.max_body_length:
            body = b''
            remaining = content_length
            while remaining > 0:
                chunk = await client_reader.read(min(1024, remaining))
                if not chunk:
                    break
                body += chunk
                remaining -= len(chunk)
        elif content_length > Request.max_body_length:
            stream = client_reader

        return Request(
            app,
            client_addr,
            method,
            url,
            http_version,
            headers,
            body=body,
            stream=stream,
            scheme=scheme,
        )


# ── Response ──────────────────────────────────────────────────────────────────


class Response:
    already_handled = None  # sentinel — never returned by this implementation

    def __init__(self, body=b'', status_code=200, headers=None, reason=None):
        self.status_code = status_code
        self.reason = reason
        self.is_head = False
        self.headers = NoCaseDict()
        if headers:
            for k, v in headers.items():
                self.headers[k] = v
        if isinstance(body, str):
            self.body = body.encode('utf-8')
            if 'content-type' not in self.headers:
                self.headers['content-type'] = 'text/plain; charset=utf-8'
        elif isinstance(body, (dict, list)):
            self.body = json.dumps(body).encode('utf-8')
            if 'content-type' not in self.headers:
                self.headers['content-type'] = 'application/json; charset=utf-8'
        else:
            self.body = body

    def complete(self):
        if isinstance(self.body, bytes) and 'content-length' not in self.headers:
            self.headers['content-length'] = str(len(self.body))

    async def body_iter(self):
        if hasattr(self.body, '__anext__'):
            async for chunk in self.body:  # type: ignore[union-attr]
                yield chunk
        elif hasattr(self.body, '__next__'):
            for chunk in self.body:
                yield chunk
        elif hasattr(self.body, 'read'):
            while True:
                chunk = self.body.read(1024)  # type: ignore[union-attr]
                if not chunk:
                    break
                yield chunk
        else:
            yield self.body if self.body else b''

    async def write(self, writer):
        reason = self.reason or _STATUS_REASONS.get(self.status_code, 'Unknown')
        await writer.awrite(f'HTTP/1.0 {self.status_code} {reason}\r\n'.encode())
        self.complete()
        for key, value in self.headers.items():
            if isinstance(value, list):
                for v in value:
                    await writer.awrite(f'{key}: {v}\r\n'.encode())
            else:
                await writer.awrite(f'{key}: {value}\r\n'.encode())
        await writer.awrite(b'\r\n')
        if not self.is_head:
            async for chunk in self.body_iter():
                if isinstance(chunk, str):
                    chunk = chunk.encode('utf-8')
                await writer.awrite(chunk)


# ── SessionAuth ───────────────────────────────────────────────────────────────


class SessionAuth:
    """Server-side session cookie authentication for MicroServer.

    Usage::

        auth = SessionAuth()

        @auth.authenticate
        async def verify(username, password):
            return username == 'admin' and password == 'secret'

        @app.get('/')
        @auth                  # HTML route — redirects to /login if not authenticated
        async def dashboard(request): ...

        @app.post('/api/data')
        @auth.api              # API route — returns 401 JSON if not authenticated
        async def data(request): ...
    """

    def __init__(
        self,
        cookie_name='session',
        timeout_ms=3_600_000,
        max_attempts=5,
        lockout_ms=60_000,
        enabled_fn=None,
    ):
        self._cookie = cookie_name
        self._timeout = timeout_ms
        self._max_attempts = max_attempts
        self._lockout_ms = lockout_ms
        self._enabled_fn = enabled_fn if enabled_fn is not None else (lambda: True)
        self._sessions = {}
        self._timestamps = {}
        self._lockout_until = 0
        self._attempts = 0
        self._verify_fn = None

    @property
    def enabled(self):
        return bool(self._enabled_fn())

    # ── Credential verification ────────────────────────────────────────────────

    def authenticate(self, f):
        """Register the credential verification function (sync or async)."""
        self._verify_fn = f
        return f

    async def verify(self, username, password):
        if self._verify_fn is None:
            return False
        result = self._verify_fn(username, password)
        if hasattr(result, 'send') and hasattr(result, 'throw'):
            return bool(await result)
        return bool(result)

    # ── Session management ─────────────────────────────────────────────────────

    def _get_token(self, request):
        return request.cookies.get(self._cookie, '')

    def _check_session(self, request):
        if not self.enabled:
            return 'anonymous'
        token = self._get_token(request)
        if not token or token not in self._sessions:
            return None
        now = _ticks_ms()
        last = self._timestamps.get(token, now)
        if _ticks_diff(now, last) > self._timeout:
            self._sessions.pop(token, None)
            self._timestamps.pop(token, None)
            return None
        self._timestamps[token] = now
        return self._sessions[token]

    def login(self, username):
        """Create a new session and return the cookie token."""
        token = binascii.hexlify(os.urandom(16)).decode()
        self._sessions[token] = username
        self._timestamps[token] = _ticks_ms()
        return token

    def logout(self, request):
        """Invalidate the session carried by this request."""
        token = self._get_token(request)
        if token:
            self._sessions.pop(token, None)
            self._timestamps.pop(token, None)

    def session_cookie(self, token):
        return f'{self._cookie}={token}; Path=/; HttpOnly; SameSite=Strict'

    def expired_cookie(self):
        return f'{self._cookie}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict'

    # ── Brute-force lockout ────────────────────────────────────────────────────

    def lockout_remaining_s(self):
        if not self._lockout_until:
            return 0
        remaining = _ticks_diff(self._lockout_until, _ticks_ms())
        if remaining <= 0:
            self._lockout_until = 0
            return 0
        return remaining // 1000 + 1

    def record_failed_attempt(self):
        """Increment failure counter. Returns lockout seconds if now locked out."""
        self._attempts += 1
        if self._attempts >= self._max_attempts:
            self._lockout_until = _ticks_add(_ticks_ms(), self._lockout_ms)
            self._attempts = 0
            return self._lockout_ms // 1000
        return 0

    def reset_attempts(self):
        self._attempts = 0
        self._lockout_until = 0

    # ── Route decorators ───────────────────────────────────────────────────────

    def __call__(self, f):
        """Protect an HTML route — redirect to /login if not authenticated."""

        async def _auth_wrapper(request, *args, **kwargs):
            if self._check_session(request) is None:
                return Response(b'', 303, headers={'Location': '/login'})
            return await f(request, *args, **kwargs)

        return _auth_wrapper

    @property
    def api(self):
        """Protect an API route — return 401 JSON if not authenticated."""

        def _decorator(f):
            async def _auth_wrapper(request, *args, **kwargs):
                if self._check_session(request) is None:
                    return Response(
                        json.dumps({'message': 'Sign in required.'}).encode(),
                        401,
                        headers={'Content-Type': 'application/json; charset=utf-8'},
                    )
                return await f(request, *args, **kwargs)

            return _auth_wrapper

        return _decorator

    @property
    def optional(self):
        """Allow access; set request.current_user to username or None."""

        def _decorator(f):
            async def _auth_wrapper(request, *args, **kwargs):
                request.current_user = self._check_session(request)
                return await f(request, *args, **kwargs)

            return _auth_wrapper

        return _decorator


# ── App ───────────────────────────────────────────────────────────────────────


class MicroServer:
    def __init__(self):
        self._routes = []
        self._after_request_handlers = []

    def route(self, url_pattern, methods=None):
        if methods is None:
            methods = ['GET']
        methods = [m.upper() for m in methods]

        def decorator(f):
            self._routes.append((URLPattern(url_pattern), methods, f))
            return f

        return decorator

    def get(self, url_pattern):
        return self.route(url_pattern, methods=['GET'])

    def post(self, url_pattern):
        return self.route(url_pattern, methods=['POST'])

    @property
    def after_request(self):
        def decorator(f):
            self._after_request_handlers.append(f)
            return f

        return decorator

    async def dispatch_request(self, request):
        if request is None:
            return Response(b'Content Too Large', 413)
        method = request.method.upper()
        response = None
        for pattern, methods, handler in self._routes:
            if method not in methods:
                continue
            params = pattern.match(request.path)
            if params is None:
                continue
            try:
                if params:
                    response = await handler(request, **params)
                else:
                    response = await handler(request)
            except Exception:
                response = Response(b'Internal Server Error', 500)
            break

        if response is None:
            response = Response(b'Not Found', 404)
        elif not isinstance(response, Response):
            if isinstance(response, tuple):
                response = Response(response[0], response[1])
            else:
                response = Response(response)

        for h in self._after_request_handlers:
            result = await h(request, response)
            if result is not None:
                response = result

        return response

    async def handle_request(self, reader, writer):
        if hasattr(writer, 'get_extra_info'):
            client_addr = writer.get_extra_info('peername', ('?', 0))
        else:
            client_addr = ('?', 0)
        request = await Request.create(self, reader, writer, client_addr)
        if request is None:
            return
        response = await self.dispatch_request(request)
        response.is_head = request.method.upper() == 'HEAD'
        await response.write(writer)
