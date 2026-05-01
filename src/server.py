"""
WiFi access-point HTTP server for pico-bit setup mode.

When GP22 is held low at boot, the device brings up an access point
configured in :mod:`device_config` and serves a browser-based editor at
``http://192.168.4.1``.  The UI lets you view, edit, save, and immediately
run the DuckyScript payload stored as ``payload.dd`` on the Pico's filesystem.

Routes
------
``GET  /``       — Main page: textarea showing current payload.dd content.
``GET  /run``    — Execute the current payload.dd via the HID keyboard.
``POST /save``   — Persist the submitted textarea content to payload.dd,
                   then redirect to ``/``.
"""

import socket
import time

import network

from device_config import AP_PASSWORD, AP_SSID, EDUCATIONAL_MODE
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
_AP_CHANNEL = 6
_kbd = None
_ap_password_in_use = AP_PASSWORD

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
        '<li>Boot with GP22 held to ground.</li>\n'
        '<li>Join the Pico access point.</li>\n'
        '<li>Edit or paste your DuckyScript.</li>\n'
        '<li>Save the file or run it after validation.</li>\n'
        '</ol>\n'
        '</section>\n'
        '<section class="panel">\n'
        '<h2 class="panel__title">Notes</h2>\n'
        '<p class="panel__body">The board scans for <code>payload.dd</code>, stores it on-device, '
        'and uses '
        'the same script in both browser setup mode and boot-time payload mode.</p>\n'
        '</section>\n'
        '</aside>\n'
        '</main>\n'
        '</div>\n'
        '</body>\n'
        '</html>',
    )
)


def _esc(s: str) -> str:
    """Escape HTML special characters for safe insertion into the template."""
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _urldecode(s: str) -> str:
    """
    Decode a URL-encoded string (``application/x-www-form-urlencoded``).

    Handles ``%XX`` percent-encoding and ``+`` → space substitution.
    """
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
    """
    Parse a URL-encoded form body into a key → value dictionary.

    :param body: Raw request body string (``k=v&k2=v2``).
    """
    params: dict[str, str] = {}
    for pair in body.split('&'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            params[_urldecode(k)] = _urldecode(v)
    return params


def _recv(conn: socket.socket) -> str:
    """
    Read a complete HTTP request from *conn* and return it as a string.

    Reads until the header separator ``\\r\\n\\r\\n`` is found, then waits
    for the full body according to ``Content-Length`` before returning.
    Silently swallows socket timeouts so the main loop stays alive.

    :param conn: Accepted client socket (timeout set to 3 s internally).
    """
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
                cl: int = 0
                for line in header_block.split('\r\n'):
                    if line.lower().startswith('content-length:'):
                        cl = int(line.split(':', 1)[1].strip())
                if len(buf) - sep >= cl:
                    break
    except OSError:
        pass
    return buf.decode('utf-8', 'ignore')


def _parse(raw: str) -> tuple[str, str, str]:
    """
    Extract the HTTP method, path, and body from a raw request string.

    Query strings are stripped from the path.  Returns ``('GET', '/', '')``
    on a malformed or empty request.

    :param raw: Full raw HTTP request as a string.
    :returns:   ``(method, path, body)`` tuple.
    """
    lines: list[str] = raw.split('\r\n')
    parts: list[str] = lines[0].split(' ') if lines else []
    method: str = parts[0] if len(parts) > 0 else 'GET'
    path: str = parts[1].split('?')[0] if len(parts) > 1 else '/'
    body: str = ''
    try:
        idx: int = raw.index('\r\n\r\n')
        body = raw[idx + 4 :]
    except ValueError:
        pass
    return method, path, body


def _send(conn: socket.socket, status: str, ctype: str, body: str | bytes) -> None:
    """
    Send an HTTP response and close the write side.

    :param conn:   Client socket.
    :param status: HTTP status line value (e.g. ``'200 OK'``).
    :param ctype:  ``Content-Type`` header value.
    :param body:   Response body; strings are UTF-8 encoded automatically.
    """
    if isinstance(body, str):
        body = body.encode()
    hdr: str = (
        f'HTTP/1.1 {status}\r\n'
        f'Content-Type: {ctype}\r\n'
        f'Content-Length: {len(body)}\r\n'
        'Connection: close\r\n\r\n'
    )
    conn.sendall(hdr.encode() + body)


def _redirect(conn: socket.socket, loc: str) -> None:
    """
    Send an HTTP 303 redirect response.

    :param conn: Client socket.
    :param loc:  ``Location`` header value (absolute or relative URL).
    """
    conn.sendall(f'HTTP/1.1 303 See Other\r\nLocation: {loc}\r\nConnection: close\r\n\r\n'.encode())


def _read_payload() -> str:
    """
    Read ``payload.dd`` from the filesystem.

    :returns: File contents, or :data:`_DEFAULT_PAYLOAD` if the file is absent.
    """
    try:
        with open(find_payload() or PAYLOAD_FILE) as f:
            return f.read()
    except OSError:
        return _DEFAULT_PAYLOAD


def _write_payload(content: str) -> None:
    """
    Overwrite ``payload.dd`` with *content*.

    :param content: New DuckyScript payload text.
    """
    with open(find_payload() or PAYLOAD_FILE, 'w') as f:
        f.write(content)


def _mode_strings() -> tuple[str, str, str]:
    """Return UI copy describing the current runtime mode."""
    if EDUCATIONAL_MODE:
        return (
            'Educational mode',
            'Educational runtime',
            'Educational mode is enabled, so higher-risk runtime features remain blocked.',
        )
    return (
        'Full runtime mode',
        'Full runtime',
        'Educational mode is disabled, so the runtime will execute its supported feature set.',
    )


def _page(message: str = '', notice: str = 'success') -> str:
    """
    Render the main HTML page, optionally showing a status message.

    :param message: Plain-text status message shown near the top of the page.
    :param notice:  Notice style token (``success`` or ``error``).
    :returns:   Rendered HTML string.
    """
    payload: str = _read_payload()
    mode_label: str
    mode_short: str
    mode_description: str
    mode_label, mode_short, mode_description = _mode_strings()
    notice_html: str = ''
    if message:
        safe_notice = _esc(notice)
        safe_message = _esc(message)
        notice_html = f'<div class="notice notice--{safe_notice}">{safe_message}</div>'
    return _HTML.format(
        notice=notice_html,
        payload=_esc(payload),
        ap_ssid=_esc(AP_SSID),
        ap_password=_esc(_ap_password_in_use or 'Open network'),
        mode_label=_esc(mode_label),
        mode_short=_esc(mode_short),
        mode_description=_esc(mode_description),
    )


def _ap_interface_id() -> int:
    """Return the AP interface constant across MicroPython network variants."""
    wlan_type = getattr(network, 'WLAN', None)
    if wlan_type is not None and hasattr(wlan_type, 'IF_AP'):
        return wlan_type.IF_AP
    return network.AP_IF


def _wlan_security(name: str, default: int) -> int:
    for owner in (getattr(network, 'WLAN', None), network):
        if owner is not None and hasattr(owner, name):
            return getattr(owner, name)
    return default


def _ap_config_attempts() -> list[tuple[str, dict[str, object]]]:
    attempts: list[tuple[str, dict[str, object]]] = []
    secure_password = AP_PASSWORD.strip()
    if secure_password:
        attempts.extend(
            [
                (
                    'wpa2',
                    {
                        'ssid': AP_SSID,
                        'channel': _AP_CHANNEL,
                        'security': _wlan_security('SEC_WPA2', 3),
                        'key': secure_password,
                    },
                ),
                (
                    'mixed-wpa',
                    {
                        'ssid': AP_SSID,
                        'channel': _AP_CHANNEL,
                        'security': _wlan_security('SEC_WPA_WPA2', 4),
                        'key': secure_password,
                    },
                ),
                (
                    'wpa2-minimal',
                    {
                        'ssid': AP_SSID,
                        'key': secure_password,
                    },
                ),
                (
                    'key-only',
                    {
                        'ssid': AP_SSID,
                        'channel': _AP_CHANNEL,
                        'key': secure_password,
                    },
                ),
                (
                    'legacy-password',
                    {
                        'essid': AP_SSID,
                        'channel': _AP_CHANNEL,
                        'password': secure_password,
                    },
                ),
                (
                    'legacy-password-minimal',
                    {
                        'essid': AP_SSID,
                        'password': secure_password,
                    },
                ),
            ]
        )
    attempts.extend(
        [
            (
                'open',
                {
                    'ssid': AP_SSID,
                    'channel': _AP_CHANNEL,
                    'security': _wlan_security('SEC_OPEN', 0),
                },
            ),
            (
                'open-minimal',
                {
                    'ssid': AP_SSID,
                },
            ),
            (
                'legacy-open',
                {
                    'essid': AP_SSID,
                    'channel': _AP_CHANNEL,
                },
            ),
            (
                'legacy-open-minimal',
                {
                    'essid': AP_SSID,
                },
            ),
        ]
    )
    return attempts


def _wlan_constant(name: str) -> object | None:
    for owner in (getattr(network, 'WLAN', None), network):
        if owner is not None and hasattr(owner, name):
            return getattr(owner, name)
    return None


def _configure_ap(ap: network.WLAN, kwargs: dict[str, object], activate_first: bool) -> str | None:
    if activate_first:
        ap.active(True)
        _sleep_ms(200)
        ap.config(**kwargs)
    else:
        ap.config(**kwargs)
        ap.active(True)

    pm_none = _wlan_constant('PM_NONE')
    if pm_none is not None:
        try:
            ap.config(pm=pm_none)
        except (AttributeError, OSError, TypeError, ValueError):
            pass

    return _wait_for_ap(ap)


def _wait_for_ap(ap: network.WLAN) -> str | None:
    for _ in range(50):
        if ap.active():
            break
        _sleep_ms(100)
    if not ap.active():
        return None
    for _ in range(30):
        ip = ap.ifconfig()[0]
        if ip and ip != '0.0.0.0':
            return ip
        _sleep_ms(100)
    return None


def _start_ap() -> str:
    """
    Bring up the WiFi access point and return the assigned IP address.

    :returns: IP address string (typically ``'192.168.4.1'``).
    :raises OSError: if the CYW43 chip is unavailable or never becomes active.
    """
    global _ap_password_in_use
    ap = network.WLAN(_ap_interface_id())
    last_error = 'no AP config attempts were made'
    attempt_index = 0

    for mode_name, kwargs in _ap_config_attempts():
        for activate_first in (False, True):
            if attempt_index:
                STATUS_LED.show('setup_ap_retry')
            attempt_index += 1
            try:
                ap.active(False)
            except OSError:
                pass
            _sleep_ms(150)
            try:
                ip = _configure_ap(ap, kwargs, activate_first=activate_first)
                if ip:
                    uses_password = 'key' in kwargs or 'password' in kwargs
                    _ap_password_in_use = AP_PASSWORD if uses_password else ''
                    return ip
                order = 'active-first' if activate_first else 'config-first'
                last_error = f'{mode_name}/{order}: interface never became ready'
            except (AttributeError, OSError, TypeError, ValueError) as exc:
                order = 'active-first' if activate_first else 'config-first'
                last_error = f'{mode_name}/{order}: {exc}'

    raise OSError(f'AP failed to come active: {last_error}')


def _ensure_keyboard():
    """Create the HID keyboard lazily so setup mode does not depend on USB init."""
    global _kbd
    if _kbd is None:
        from hid import HIDKeyboard

        _kbd = HIDKeyboard()
    if not _kbd.wait_open(_USB_ENUM_TIMEOUT_MS):
        raise OSError('USB HID did not enumerate within 5 s')
    return _kbd


def start() -> None:
    """
    Start the setup-mode HTTP server (blocking).

    Brings up the WiFi AP, binds a TCP socket on port 80, and enters the
    request loop.  Individual request errors are printed and discarded so
    the server remains alive.
    """
    STATUS_LED.show('setup_ap_starting')
    _start_ap()
    STATUS_LED.show('setup_ap_ready')

    srv: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', PORT))
        srv.listen(3)
    except OSError as exc:
        srv.close()
        raise RuntimeError('setup server bind failed') from exc

    STATUS_LED.show('setup_server_ready')
    STATUS_LED.on()

    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            continue

        try:
            raw: str = _recv(conn)
            method: str
            path: str
            body: str
            method, path, body = _parse(raw)

            if path == '/':
                _send(conn, '200 OK', 'text/html', _page())

            elif path == '/run':
                script: str = _read_payload()
                try:
                    validate_script(script)
                    kbd = _ensure_keyboard()
                    run_script(kbd, script, educational_mode=EDUCATIONAL_MODE)
                    _send(conn, '200 OK', 'text/html', _page('Payload executed', 'success'))
                except DuckyScriptError as exc:
                    _send(conn, '200 OK', 'text/html', _page(f'Error: {exc}', 'error'))
                except OSError as exc:
                    _send(conn, '200 OK', 'text/html', _page(f'USB error: {exc}', 'error'))

            elif path == '/save' and method == 'POST':
                content: str = _parse_form(body).get('p', '').replace('\r\n', '\n')
                _write_payload(content)
                _redirect(conn, '/')

            else:
                _send(conn, '404 Not Found', 'text/plain', '404')

        except Exception as e:
            print('request error:', e)
            pass
        finally:
            conn.close()
