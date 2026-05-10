import time

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
_LOOT_FILE = 'loot.json'
_STATIC_DIR = 'static'
_PAYLOAD_BIN = 'pico-agent'
_MAX_BINARY_SIZE = 2 * 1024 * 1024
_FILE_CHUNK_SIZE = 4096
_JSON_HEADERS = {'Content-Type': 'application/json; charset=utf-8'}
_NO_STORE = {'Cache-Control': 'no-store'}
_STATIC_CACHE = {'Cache-Control': 'public, max-age=86400'}


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


async def _read_request_headers(reader):
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

    target = parts[1]
    path = target.split('?', 1)[0]
    return {
        'method': parts[0].upper(),
        'path': path,
        'target': target,
        'headers': headers,
        'cookies': _parse_cookies(headers.get('cookie', '')),
    }
