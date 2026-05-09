import time

PORT = 80
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
_LOOT_FILE = 'loot.json'
_STATIC_DIR = 'static'
_PAYLOAD_BIN = 'static/payload.bin'
_MAX_BINARY_SIZE = 2 * 1024 * 1024
_FILE_CHUNK_SIZE = 4096


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _urldecode(s):
    out = []
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


def _parse_form(body):
    params = {}
    for pair in body.decode('utf-8', 'ignore').split('&'):
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        params[_urldecode(key)] = _urldecode(value)
    return params


def _ticks_ms():
    fn = getattr(time, 'ticks_ms', None)
    if callable(fn):
        return int(fn())  # type: ignore
    return int(time.monotonic() * 1000)


def _ticks_add(t, delta):
    fn = getattr(time, 'ticks_add', None)
    if callable(fn):
        return int(fn(t, delta))  # type: ignore
    return t + delta


def _ticks_diff(end, start):
    fn = getattr(time, 'ticks_diff', None)
    if callable(fn):
        return int(fn(end, start))  # type: ignore
    return end - start
