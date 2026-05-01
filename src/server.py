import socket
import time

import network

from device_config import ALLOW_UNSAFE, AP_PASSWORD, AP_SSID
from ducky import (
    PAYLOAD_FILE,
    DuckyScriptError,
    find_payload,
    run_script,
    validate_script,
)
from status_led import STATUS_LED

PORT: int = 80
_USB_ENUM_TIMEOUT_MS = 5000
_DEFAULT_AP_IP = '192.168.4.1'

if hasattr(time, 'sleep_ms'):
    _sleep_ms = time.sleep_ms  # type: ignore[attr-defined]
else:

    def _sleep_ms(ms: int) -> None:
        time.sleep(ms / 1000)


_DEFAULT_PAYLOAD: str = (
    'REM picoDucky default payload\nDELAY 1000\nGUI SPACE\nDELAY 800\nSTRING Calculator\nENTER\n'
)

_HTML: str = ''.join(
    (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>Pico Bit</title>\n'
        '<style>\n'
        ':root{{color-scheme:light;--page:#fff;--ink:#111;--muted:#6b7280;--line:#e5e7eb;'
        '--soft:#f5f5f4;--shadow:0 24px 60px rgba(15,23,42,.08);--radius:28px;'
        '--sans:"Avenir Next","Helvetica Neue","Segoe UI",sans-serif;'
        '--mono:"SFMono-Regular",Monaco,"Cascadia Mono","Segoe UI Mono",monospace}}\n'
        '*{{box-sizing:border-box}}\n'
        'html,body{{margin:0;min-height:100%;background:var(--page);color:var(--ink)}}\n'
        'body{{font-family:var(--sans);background-image:'
        'radial-gradient(circle at top,#f6f6f4 0,#fff 42%)}}\n'
        'a{{color:inherit}}\n'
        '.app{{max-width:1180px;margin:0 auto;padding:28px 18px 40px}}\n'
        '.hero{{display:grid;gap:18px;margin-bottom:24px}}\n'
        '.hero__copy{{padding:8px 0}}\n'
        '.hero__eyebrow{{margin:0 0 12px;font-size:12px;font-weight:700;letter-spacing:.16em;'
        'text-transform:uppercase;color:#52525b}}\n'
        '.hero__title{{margin:0;font-size:clamp(34px,5vw,56px);line-height:1.02;'
        'letter-spacing:-.04em}}\n'
        '.hero__body{{max-width:640px;margin:14px 0 0;font-size:16px;line-height:1.7;'
        'color:#52525b}}\n'
        '.hero__card{{background:linear-gradient(180deg,#fff,#fafaf9);border:1px solid var(--line);'
        'border-radius:var(--radius);padding:22px;box-shadow:var(--shadow)}}\n'
        '.hero__grid{{display:grid;gap:14px}}\n'
        '.metric{{padding:14px 16px;border:1px solid var(--line);border-radius:16px;'
        'background:#fff}}\n'
        '.metric__label{{display:block;margin-bottom:6px;font-size:11px;font-weight:700;letter-spacing:.14em;'
        'text-transform:uppercase;color:var(--muted)}}\n'
        '.metric__value{{display:block;font-size:16px;font-weight:700;letter-spacing:-.02em}}\n'
        '.metric__value--mono{{font-family:var(--mono);font-size:14px}}\n'
        '.notice{{margin:0 0 18px;padding:14px 16px;border-radius:16px;'
        'border:1px solid var(--line);'
        'font-size:14px;line-height:1.6;background:#fafaf9}}\n'
        '.notice--success{{border-color:#d4d4d8;background:#fafaf9}}\n'
        '.notice--error{{border-color:#fecaca;background:#fef2f2}}\n'
        '.workspace{{display:grid;gap:20px}}\n'
        '.editor{{background:#fff;border:1px solid var(--line);'
        'border-radius:var(--radius);overflow:hidden;'
        'box-shadow:var(--shadow)}}\n'
        '.editor__chrome{{display:flex;align-items:center;gap:14px;padding:16px 18px;'
        'border-bottom:1px solid var(--line);background:linear-gradient(180deg,#fff,#fafaf9)}}\n'
        '.editor__lights{{display:flex;gap:8px;flex-shrink:0}}\n'
        '.editor__lights span{{display:block;width:10px;height:10px;'
        'border-radius:999px;background:#111}}\n'
        '.editor__file{{padding:8px 12px;border-radius:999px;background:#111;color:#fff;'
        'font-size:13px;font-weight:700;letter-spacing:-.01em}}\n'
        '.editor__hint{{margin-left:auto;font-size:13px;color:var(--muted)}}\n'
        '.editor__form{{padding:18px}}\n'
        '.editor__toolbar{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;margin-bottom:16px}}\n'
        '.editor__pills{{display:flex;flex-wrap:wrap;gap:10px}}\n'
        '.pill{{display:inline-flex;align-items:center;padding:8px 12px;'
        'border:1px solid var(--line);'
        'border-radius:999px;background:#fafaf9;font-size:12px;font-weight:700;color:#3f3f46}}\n'
        '.editor__actions{{display:flex;flex-wrap:wrap;gap:10px}}\n'
        '.button{{display:inline-flex;align-items:center;justify-content:center;padding:12px 18px;'
        'border-radius:14px;border:1px solid #111;background:#111;color:#fff;font-size:14px;'
        'font-weight:700;text-decoration:none;cursor:pointer;transition:transform .12s ease,'
        'box-shadow .12s ease,background .12s ease}}\n'
        '.button:active{{transform:translateY(1px)}}\n'
        '.button--secondary{{background:#fff;color:#111;border-color:var(--line)}}\n'
        '.editor__surface{{display:grid;grid-template-columns:70px 1fr;gap:0;'
        'border:1px solid var(--line);'
        'border-radius:22px;background:#fff;overflow:hidden}}\n'
        '.editor__rail{{display:flex;flex-direction:column;justify-content:space-between;gap:18px;'
        'padding:18px 12px;background:#fafaf9;border-right:1px solid var(--line);'
        'font:700 11px/1.4 var(--mono);'
        'letter-spacing:.16em;text-transform:uppercase;color:#71717a}}\n'
        '.editor__rail span{{display:block}}\n'
        '.editor__input{{width:100%;min-height:560px;padding:22px;border:0;outline:none;resize:vertical;'
        'background:linear-gradient(180deg,#fff,#fcfcfb);color:#111;font:14px/1.7 var(--mono);'
        'tab-size:4;'
        'white-space:pre;overflow:auto}}\n'
        '.editor__input::placeholder{{color:#a1a1aa}}\n'
        '.editor__footer{{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;'
        'gap:14px;margin-top:16px}}\n'
        '.editor__note{{margin:0;max-width:540px;font-size:14px;line-height:1.7;color:var(--muted)}}\n'
        '.sidebar{{display:grid;gap:18px}}\n'
        '.panel{{padding:22px;border:1px solid var(--line);border-radius:24px;background:#fff;'
        'box-shadow:0 18px 40px rgba(15,23,42,.05)}}\n'
        '.panel__title{{margin:0 0 12px;font-size:17px;letter-spacing:-.02em}}\n'
        '.panel__body{{margin:0;font-size:14px;line-height:1.7;color:#52525b}}\n'
        '.steps{{margin:0;padding-left:20px;font-size:14px;line-height:1.8;color:#27272a}}\n'
        '@media (min-width:980px){{.hero{{grid-template-columns:1.45fr .95fr;align-items:end}}'
        '.workspace{{grid-template-columns:minmax(0,1.65fr) minmax(280px,.85fr);'
        'align-items:start}}}}\n'
        '@media (max-width:720px){{.app{{padding:22px 14px 32px}}'
        '.editor__surface{{grid-template-columns:1fr}}'
        '.editor__rail{{display:none}}.editor__input{{min-height:420px}}.button{{width:100%}}'
        '.editor__actions{{width:100%}}.editor__actions .button{{flex:1}}}}\n'
        '</style>\n'
        '</head>\n'
        '<body>\n'
        '<div class="app">\n'
        '<header class="hero">\n'
        '<div class="hero__copy">\n'
        '<p class="hero__eyebrow">pico-bit setup</p>\n'
        '<h1 class="hero__title">A clean browser editor for <span>payload.dd</span>.</h1>\n'
        '<p class="hero__body">Write, save, validate, and run your DuckyScript from a Pico 2 W '
        'access point without leaving the browser. The workspace is tuned for a keyboard-driven '
        'flow and ships '
        'as part of the single-file MicroPython bundle.</p>\n'
        '</div>\n'
        '<aside class="hero__card">\n'
        '<div class="hero__grid">\n'
        '<div class="metric"><span class="metric__label">Access point</span>'
        '<strong class="metric__value">{ap_ssid}</strong></div>\n'
        '<div class="metric"><span class="metric__label">Password</span>'
        '<strong class="metric__value metric__value--mono">{ap_password}</strong></div>\n'
        '<div class="metric"><span class="metric__label">Runtime mode</span>'
        '<strong class="metric__value">{mode_label}</strong></div>\n'
        '<div class="metric"><span class="metric__label">Target file</span>'
        '<strong class="metric__value metric__value--mono">payload.dd</strong></div>\n'
        '</div>\n'
        '</aside>\n'
        '</header>\n'
        '{notice}\n'
        '<main class="workspace">\n'
        '<section class="editor">\n'
        '<div class="editor__chrome">\n'
        '<div class="editor__lights"><span></span><span></span><span></span></div>\n'
        '<div class="editor__file">payload.dd</div>\n'
        '<div class="editor__hint">MicroPython setup portal</div>\n'
        '</div>\n'
        '<form class="editor__form" method="POST" action="/save">\n'
        '<div class="editor__toolbar">\n'
        '<div class="editor__pills">\n'
        '<span class="pill">Saved on device</span>\n'
        '<span class="pill">Validated before run</span>\n'
        '<span class="pill">{mode_short}</span>\n'
        '</div>\n'
        '<div class="editor__actions">\n'
        '<a class="button button--secondary" href="/">Refresh</a>\n'
        '<a class="button" href="/run">Run payload</a>\n'
        '</div>\n'
        '</div>\n'
        '<div class="editor__surface">\n'
        '<div class="editor__rail"><span>DD</span><span>EDIT</span><span>RUN</span></div>\n'
        '<textarea class="editor__input" name="p" spellcheck="false" autocapitalize="off" '
        'autocomplete="off" autocorrect="off" '
        'placeholder="REM Write your payload here">{payload}</textarea>\n'
        '</div>\n'
        '<div class="editor__footer">\n'
        '<p class="editor__note">{mode_description} Parse errors stop execution before runtime '
        'so a '
        'broken '
        'payload never silently fires.</p>\n'
        '<button class="button" type="submit">Save payload</button>\n'
        '</div>\n'
        '</form>\n'
        '</section>\n'
        '<aside class="sidebar">\n'
        '<section class="panel">\n'
        '<h2 class="panel__title">Workflow</h2>\n'
        '<ol class="steps">\n'
        '<li>Power on the Pico.</li>\n'
        '<li>Join the Pico access point.</li>\n'
        '<li>Edit or paste your DuckyScript.</li>\n'
        '<li>Save the file or run it after validation.</li>\n'
        '</ol>\n'
        '</section>\n'
        '<section class="panel">\n'
        '<h2 class="panel__title">Notes</h2>\n'
        '<p class="panel__body">The board scans for <code>payload.dd</code>, stores it on-device, '
        'and keeps '
        'the browser portal available while the boot payload runs.</p>\n'
        '</section>\n'
        '</aside>\n'
        '</main>\n'
        '</div>\n'
        '</body>\n'
        '</html>',
    )
)

__all__ = ['SetupServer', 'SERVER', 'start']


def _esc(s: str) -> str:
    """Escape text for the HTML template."""
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _urldecode(s: str) -> str:
    """Decode a form-encoded string."""
    out: list[str] = []
    i: int = 0
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


def _parse_form(body: str) -> dict[str, str]:
    """Parse a small x-www-form-urlencoded body."""
    params: dict[str, str] = {}
    for pair in body.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[_urldecode(key)] = _urldecode(value)
    return params


def _recv(conn: socket.socket) -> str:
    """Read one HTTP request, including any declared body."""
    conn.settimeout(3.0)
    buf: bytes = b''
    try:
        while True:
            chunk: bytes = conn.recv(1024)
            if not chunk:
                break
            buf += chunk
            if b'\r\n\r\n' in buf:
                sep: int = buf.index(b'\r\n\r\n') + 4
                header_block: str = buf[:sep].decode('utf-8', 'ignore')
                content_length: int = 0
                for line in header_block.split('\r\n'):
                    if line.lower().startswith('content-length:'):
                        content_length = int(line.split(':', 1)[1].strip())
                if len(buf) - sep >= content_length:
                    break
    except OSError:
        pass
    return buf.decode('utf-8', 'ignore')


def _parse(raw: str) -> tuple[str, str, str]:
    """Split a raw request into method, path, and body."""
    lines: list[str] = raw.split('\r\n')
    parts: list[str] = lines[0].split(' ') if lines else []
    method: str = parts[0] if parts else 'GET'
    path: str = parts[1].split('?')[0] if len(parts) > 1 else '/'
    body: str = ''
    try:
        body = raw[raw.index('\r\n\r\n') + 4 :]
    except ValueError:
        pass
    return method, path, body


def _send(conn: socket.socket, status: str, ctype: str, body: str | bytes) -> None:
    """Send an HTTP response."""
    if isinstance(body, str):
        body = body.encode()
    headers: str = (
        f'HTTP/1.1 {status}\r\n'
        f'Content-Type: {ctype}\r\n'
        f'Content-Length: {len(body)}\r\n'
        'Connection: close\r\n\r\n'
    )
    conn.sendall(headers.encode() + body)


def _redirect(conn: socket.socket, loc: str) -> None:
    """Send a 303 redirect."""
    conn.sendall(f'HTTP/1.1 303 See Other\r\nLocation: {loc}\r\nConnection: close\r\n\r\n'.encode())


class SetupServer:
    """Setup-mode portal for editing and running payload.dd."""

    def __init__(self, port: int = PORT) -> None:
        self.port = port
        self._ap = None
        self._kbd = None
        self._ap_password_in_use = AP_PASSWORD
        self._run_lock = None
        self._server_socket = None
        self._server_thread_started = False
        self._thread_mod = None

    def _read_payload(self) -> str:
        """Load payload.dd, or fall back to the bundled starter script."""
        try:
            with open(find_payload() or PAYLOAD_FILE) as f:
                return f.read()
        except OSError:
            return _DEFAULT_PAYLOAD

    def _write_payload(self, content: str) -> None:
        """Persist the current payload text."""
        with open(find_payload() or PAYLOAD_FILE, 'w') as f:
            f.write(content)

    def _mode_strings(self) -> tuple[str, str, str]:
        """Return the labels shown for the current runtime mode."""
        if ALLOW_UNSAFE:
            return (
                'Unsafe mode allowed',
                'Unsafe runtime enabled',
                'Allow unsafe is enabled, so supported unsafe runtime features may execute.',
            )
        return (
            'Safe mode',
            'Unsafe runtime blocked',
            'Allow unsafe is disabled, so higher-risk runtime features stay blocked.',
        )

    def _page(self, message: str = '', notice: str = 'success') -> str:
        """Render the setup page."""
        mode_label, mode_short, mode_description = self._mode_strings()
        notice_html = ''
        if message:
            notice_html = f'<div class="notice notice--{_esc(notice)}">{_esc(message)}</div>'
        return _HTML.format(
            notice=notice_html,
            payload=_esc(self._read_payload()),
            ap_ssid=_esc(AP_SSID),
            ap_password=_esc(self._ap_password_in_use or 'Open network'),
            mode_label=_esc(mode_label),
            mode_short=_esc(mode_short),
            mode_description=_esc(mode_description),
        )

    def _start_ap(self) -> str:
        """Start the AP and return its IP address."""
        ap = network.WLAN(network.AP_IF)
        self._ap = ap
        try:
            ap.active(False)
        except OSError:
            pass
        _sleep_ms(150)

        # Match abc.py exactly: essid=... and config before active(True).
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
            _sleep_ms(100)
        if not ap.active():
            raise OSError('AP failed to come active within 5 s')

        for _ in range(20):
            try:
                ip = ap.ifconfig()[0]
            except (AttributeError, OSError, TypeError, ValueError):
                ip = ''
            if ip and ip != '0.0.0.0':
                return ip
            _sleep_ms(100)
        return _DEFAULT_AP_IP

    def _thread_module(self):
        if self._thread_mod is None:
            self._thread_mod = __import__('_thread')
        return self._thread_mod

    def _run_lock_obj(self):
        if self._run_lock is None:
            self._run_lock = self._thread_module().allocate_lock()
        return self._run_lock

    def acquire_execution(self) -> None:
        """Serialize HID use across boot payloads and browser-triggered runs."""
        self._run_lock_obj().acquire()

    def release_execution(self) -> None:
        self._run_lock_obj().release()

    def _keyboard(self):
        """Create HID lazily so the AP can start before USB is ready."""
        if self._kbd is None:
            from hid import HIDKeyboard

            self._kbd = HIDKeyboard()
        return self._kbd

    def keyboard(self):
        """Return the shared HID keyboard without waiting for enumeration."""
        return self._keyboard()

    def _ensure_keyboard(self):
        """Return a shared keyboard once the host has enumerated HID."""
        keyboard = self._keyboard()
        if not keyboard.wait_open(_USB_ENUM_TIMEOUT_MS):
            raise OSError('USB HID did not enumerate within 5 s')
        return keyboard

    def execute_script(self, script: str, allow_unsafe: bool = ALLOW_UNSAFE) -> None:
        """Validate and run a script with exclusive access to the HID device."""
        self.acquire_execution()
        try:
            validate_script(script)
            keyboard = self._ensure_keyboard()
            run_script(keyboard, script, allow_unsafe=allow_unsafe)
        finally:
            self.release_execution()

    def _prepare_server(self) -> None:
        """Start the AP and bind the listening socket once."""
        if self._server_socket is not None:
            return

        STATUS_LED.show('setup_ap_starting')
        self._start_ap()
        STATUS_LED.show('setup_ap_ready')

        srv: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(('0.0.0.0', self.port))
            srv.listen(3)
            srv.settimeout(0.2)
        except OSError as exc:
            srv.close()
            raise RuntimeError('setup server bind failed') from exc

        self._server_socket = srv
        STATUS_LED.show('setup_server_ready')
        STATUS_LED.on()

    def _serve_forever(self) -> None:
        """Serve requests until the process exits."""
        srv = self._server_socket
        if srv is None:
            raise RuntimeError('server socket not prepared')

        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                continue

            try:
                self._handle_request(conn)
            except Exception as exc:
                print('request error:', exc)
            finally:
                conn.close()

    def _run_payload(self) -> tuple[str, str]:
        """Validate and run the saved payload."""
        script = self._read_payload()
        try:
            self.execute_script(script, allow_unsafe=ALLOW_UNSAFE)
            return 'Payload executed', 'success'
        except DuckyScriptError as exc:
            return f'Error: {exc}', 'error'
        except OSError as exc:
            return f'USB error: {exc}', 'error'

    def _handle_request(self, conn: socket.socket) -> None:
        """Route one browser request."""
        method, path, body = _parse(_recv(conn))

        if path == '/':
            _send(conn, '200 OK', 'text/html', self._page())
            return

        if path == '/run':
            message, notice = self._run_payload()
            _send(conn, '200 OK', 'text/html', self._page(message, notice))
            return

        if path == '/save' and method == 'POST':
            content = _parse_form(body).get('p', '').replace('\r\n', '\n')
            self._write_payload(content)
            _redirect(conn, '/')
            return

        _send(conn, '404 Not Found', 'text/plain', '404')

    def start(self) -> None:
        """Start the setup AP and serve requests forever."""
        if self._server_thread_started:
            raise RuntimeError('setup server is already running in the background')
        self._prepare_server()
        self._serve_forever()

    def start_background(self) -> None:
        """Start the AP and serve requests on a background thread."""
        if self._server_thread_started:
            return
        self._prepare_server()
        self._thread_module().start_new_thread(self._serve_forever, ())
        self._server_thread_started = True


SERVER = SetupServer()


def start() -> None:
    """Backward-compatible entry point for setup mode."""
    SERVER.start()
