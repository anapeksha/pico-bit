"""USB HID keyboard helpers for MicroPython on the Raspberry Pi Pico 2."""

import machine

from helpers import sleep_ms, sleep_ms_blocking
from keyboard_layouts import DEFAULT_LAYOUT_CODE, lookup_char_steps

MOD_NONE = 0x00
MOD_CTRL = 0x01
MOD_SHIFT = 0x02
MOD_ALT = 0x04
MOD_GUI = 0x08
MOD_ALTGR = 0x40

KEY_ENTER = 0x28
KEY_SPACE = 0x2C

_MOD_LEFT_CTRL = 0xE0
_MOD_LEFT_SHIFT = 0xE1
_MOD_LEFT_ALT = 0xE2
_MOD_LEFT_GUI = 0xE3
_MOD_RIGHT_CTRL = 0xE4
_MOD_RIGHT_SHIFT = 0xE5
_MOD_RIGHT_ALT = 0xE6
_MOD_RIGHT_GUI = 0xE7

# Canonical HID Boot Keyboard descriptor — matches MicroPython's official
# usb.device.keyboard exactly (Logical/Usage Max = 101, the highest valid
# keycode in Usage Page 0x07). Earlier versions used 255 which required
# 16-bit encoding; macOS occasionally rejects nonstandard variants, so we
# match upstream byte-for-byte.
_REPORT_DESC = bytes(
    [
        0x05,
        0x01,  # Usage Page (Generic Desktop)
        0x09,
        0x06,  # Usage (Keyboard)
        0xA1,
        0x01,  # Collection (Application)
        0x05,
        0x07,  # Usage Page (Keyboard/Keypad)
        0x19,
        0xE0,  # Usage Minimum (Left Control)
        0x29,
        0xE7,  # Usage Maximum (Right GUI)
        0x15,
        0x00,  # Logical Minimum (0)
        0x25,
        0x01,  # Logical Maximum (1)
        0x75,
        0x01,  # Report Size (1)
        0x95,
        0x08,  # Report Count (8)
        0x81,
        0x02,  # Input (Data, Var, Abs) — modifier byte
        0x95,
        0x01,  # Report Count (1)
        0x75,
        0x08,  # Report Size (8)
        0x81,
        0x01,  # Input (Constant) — reserved
        0x95,
        0x05,  # Report Count (5)
        0x75,
        0x01,  # Report Size (1)
        0x05,
        0x08,  # Usage Page (LEDs)
        0x19,
        0x01,  # Usage Minimum (Num Lock)
        0x29,
        0x05,  # Usage Maximum (Kana)
        0x91,
        0x02,  # Output (Data, Var, Abs)
        0x95,
        0x01,  # Report Count (1)
        0x75,
        0x03,  # Report Size (3)
        0x91,
        0x01,  # Output (Constant) — LED padding
        0x95,
        0x06,  # Report Count (6)
        0x75,
        0x08,  # Report Size (8)
        0x15,
        0x00,  # Logical Minimum (0)
        0x25,
        0x65,  # Logical Maximum (101)
        0x05,
        0x07,  # Usage Page (Keyboard/Keypad)
        0x19,
        0x00,  # Usage Minimum (0)
        0x29,
        0x65,  # Usage Maximum (101)
        0x81,
        0x00,  # Input (Data, Array)
        0xC0,  # End Collection
    ]
)

_RD_LEN_LO = len(_REPORT_DESC) & 0xFF
_RD_LEN_HI = (len(_REPORT_DESC) >> 8) & 0xFF

_DEVICE_DESC = bytes(
    [
        0x12,
        0x01,
        0x00,
        0x02,
        0x00,
        0x00,
        0x00,
        0x40,
        0x5E,
        0x04,
        0x50,
        0x07,
        0x01,
        0x01,
        0x01,
        0x02,
        0x03,
        0x01,
    ]
)

_TOTAL_CFG = 9 + 9 + 9 + 7

_CONFIG_DESC = bytes(
    [
        0x09,
        0x02,
        _TOTAL_CFG,
        0x00,
        0x01,
        0x01,
        0x00,
        0xA0,
        0x32,
        0x09,
        0x04,
        0x00,
        0x00,
        0x01,
        0x03,
        0x01,
        0x01,
        0x00,
        0x09,
        0x21,
        0x11,
        0x01,
        0x00,
        0x01,
        0x22,
        _RD_LEN_LO,
        _RD_LEN_HI,
        0x07,
        0x05,
        0x81,
        0x03,
        0x08,
        0x00,
        0x0A,
    ]
)

# Descriptor index 0 is the language descriptor. Returning None there tells
# MicroPython to provide the default English language descriptor, while indexes
# 1..3 map to iManufacturer/iProduct/iSerial from _DEVICE_DESC.
_STRING_DESCS = [None, 'Microsoft', 'Wired Keyboard 600', '000000000001']


def _u16le(value):
    return value & 0xFF, (value >> 8) & 0xFF


def _hid_config_desc(interface, endpoint_in, string_index):
    total_cfg = 9 + 9 + 7
    total_lo, total_hi = _u16le(total_cfg)
    return bytes(
        [
            0x09,
            0x02,
            total_lo,
            total_hi,
            0x01,
            0x01,
            0x00,
            0xA0,
            0x32,
            0x09,
            0x04,
            interface,
            0x00,
            0x01,
            0x03,
            0x01,
            0x01,
            string_index,
            0x09,
            0x21,
            0x11,
            0x01,
            0x00,
            0x01,
            0x22,
            _RD_LEN_LO,
            _RD_LEN_HI,
            0x07,
            0x05,
            endpoint_in,
            0x03,
            0x08,
            0x00,
            0x0A,
        ]
    )


def _builtin_msc_driver(dev):
    for name in ('BUILTIN_MSC', 'BUILTIN_CDC_MSC'):
        driver = getattr(dev, name, None)
        if driver is not None:
            return driver
    return None


def _usb_config(dev):
    builtin = _builtin_msc_driver(dev)
    if builtin is None:
        return dev.BUILTIN_NONE, _DEVICE_DESC, _CONFIG_DESC, _STRING_DESCS, 0, 0x81

    interface = int(builtin.itf_max)
    endpoint_num = max(int(builtin.ep_max), 1)
    string_index = int(builtin.str_max)
    endpoint_in = 0x80 | endpoint_num

    hid_cfg = _hid_config_desc(interface, endpoint_in, string_index)[9:]
    cfg = bytearray(builtin.desc_cfg)
    total_len = len(cfg) + len(hid_cfg)
    cfg[2], cfg[3] = _u16le(total_len)
    cfg[4] = interface + 1
    cfg.extend(hid_cfg)

    desc_strs = {0: None, string_index: 'Wired Keyboard 600'}
    return builtin, builtin.desc_dev, bytes(cfg), desc_strs, interface, endpoint_in


def _letter_keycode(ch):
    return 0x04 + ord(ch) - ord('a')


def _digit_keycode(ch):
    return {
        '1': 0x1E,
        '2': 0x1F,
        '3': 0x20,
        '4': 0x21,
        '5': 0x22,
        '6': 0x23,
        '7': 0x24,
        '8': 0x25,
        '9': 0x26,
        '0': 0x27,
    }[ch]


_BASE_CHAR_KEYS = {
    ' ': 0x2C,
    '-': 0x2D,
    '=': 0x2E,
    '[': 0x2F,
    ']': 0x30,
    '\\': 0x31,
    ';': 0x33,
    "'": 0x34,
    '`': 0x35,
    ',': 0x36,
    '.': 0x37,
    '/': 0x38,
}

for _ch in 'abcdefghijklmnopqrstuvwxyz':
    _BASE_CHAR_KEYS[_ch] = _letter_keycode(_ch)

for _ch in '1234567890':
    _BASE_CHAR_KEYS[_ch] = _digit_keycode(_ch)

_SHIFTED_FROM_BASE = {
    '_': '-',
    '+': '=',
    '{': '[',
    '}': ']',
    '|': '\\',
    ':': ';',
    '"': "'",
    '~': '`',
    '<': ',',
    '>': '.',
    '?': '/',
    '!': '1',
    '@': '2',
    '#': '3',
    '$': '4',
    '%': '5',
    '^': '6',
    '&': '7',
    '*': '8',
    '(': '9',
    ')': '0',
}

_CHAR_MAP = {}
for _ch, _keycode in _BASE_CHAR_KEYS.items():
    _CHAR_MAP[_ch] = (MOD_NONE, _keycode)

for _ch in 'abcdefghijklmnopqrstuvwxyz':
    _CHAR_MAP[_ch.upper()] = (MOD_SHIFT, _BASE_CHAR_KEYS[_ch])

for _shifted, _base in _SHIFTED_FROM_BASE.items():
    _CHAR_MAP[_shifted] = (MOD_SHIFT, _BASE_CHAR_KEYS[_base])

KEY_ALIASES = {
    'APP': 0x65,
    'APPLICATION': 0x65,
    'BACKSLASH': 0x31,
    'BACKSPACE': 0x2A,
    'BREAK': 0x48,
    'CAPSLOCK': 0x39,
    'COMMA': 0x36,
    'DELETE': 0x4C,
    'DEL': 0x4C,
    'DOT': 0x37,
    'DOWN': 0x51,
    'DOWNARROW': 0x51,
    'END': 0x4D,
    'ENTER': KEY_ENTER,
    'ESC': 0x29,
    'ESCAPE': 0x29,
    'EQUAL': 0x2E,
    'F1': 0x3A,
    'F2': 0x3B,
    'F3': 0x3C,
    'F4': 0x3D,
    'F5': 0x3E,
    'F6': 0x3F,
    'F7': 0x40,
    'F8': 0x41,
    'F9': 0x42,
    'F10': 0x43,
    'F11': 0x44,
    'F12': 0x45,
    'F13': 0x68,
    'F14': 0x69,
    'F15': 0x6A,
    'F16': 0x6B,
    'F17': 0x6C,
    'F18': 0x6D,
    'F19': 0x6E,
    'F20': 0x6F,
    'F21': 0x70,
    'F22': 0x71,
    'F23': 0x72,
    'F24': 0x73,
    'GRAVE': 0x35,
    'HOME': 0x4A,
    'INSERT': 0x49,
    'LEFT': 0x50,
    'LEFTARROW': 0x50,
    'LEFTBRACE': 0x2F,
    'LEFTBRACKET': 0x2F,
    'MENU': 0x65,
    'MINUS': 0x2D,
    'NUMLOCK': 0x53,
    'PAGEDOWN': 0x4E,
    'PAGEDN': 0x4E,
    'PAGEUP': 0x4B,
    'PGDN': 0x4E,
    'PGUP': 0x4B,
    'PAUSE': 0x48,
    'PERIOD': 0x37,
    'PRINTSCREEN': 0x46,
    'PRTSC': 0x46,
    'QUOTE': 0x34,
    'RETURN': KEY_ENTER,
    'RIGHT': 0x4F,
    'RIGHTARROW': 0x4F,
    'RIGHTBRACE': 0x30,
    'RIGHTBRACKET': 0x30,
    'SCROLLLOCK': 0x47,
    'SEMICOLON': 0x33,
    'SLASH': 0x38,
    'SPACE': KEY_SPACE,
    'TAB': 0x2B,
    'UP': 0x52,
    'UPARROW': 0x52,
}

for _ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    KEY_ALIASES[_ch] = _BASE_CHAR_KEYS[_ch.lower()]

for _ch in '1234567890':
    KEY_ALIASES[_ch] = _BASE_CHAR_KEYS[_ch]

MOD_ALIASES = {
    'ALT': MOD_ALT,
    'COMMAND': MOD_GUI,
    'CMD': MOD_GUI,
    'CONTROL': MOD_CTRL,
    'CTRL': MOD_CTRL,
    'GUI': MOD_GUI,
    'OPTION': MOD_ALT,
    'OPT': MOD_ALT,
    'SHIFT': MOD_SHIFT,
    'WINDOWS': MOD_GUI,
    'WIN': MOD_GUI,
}


def _normalize_token(token):
    return token.strip().upper().replace('_', '')


def lookup_char(ch, layout_code=DEFAULT_LAYOUT_CODE):
    steps = lookup_char_steps(ch, layout_code)
    if steps:
        return steps[0]
    return MOD_NONE, 0


def lookup_keycode(token):
    token = _normalize_token(token)
    return KEY_ALIASES.get(token, 0)


def resolve_key_token(token):
    token = token.strip()
    keycode = lookup_keycode(token)
    if keycode:
        return MOD_NONE, keycode
    if len(token) == 1:
        if token.isalpha():
            return _CHAR_MAP.get(token.lower(), (MOD_NONE, 0))
        return _CHAR_MAP.get(token, (MOD_NONE, 0))
    return MOD_NONE, 0


class HIDKeyboard:
    def __init__(self):
        self._ready = False
        self._xfer_busy = False
        self._submit_failures = 0
        self._submit_total = 0
        self._report = bytearray(8)
        self._held_modifiers = 0
        self._held_keys = []
        self._dev = machine.USBDevice()
        self._builtin_driver, desc_dev, desc_cfg, desc_strs, self._itf, self._ep_in = _usb_config(
            self._dev
        )

        def _control_cb(stage, request):
            bm = request[0]
            req = request[1]
            wv = request[2] | (request[3] << 8)
            wi = request[4] | (request[5] << 8)
            if stage == 1:
                if bm == 0x81 and req == 0x06 and (wv >> 8) == 0x22 and wi == self._itf:
                    # Host requested the HID report descriptor — enumeration is
                    # actively in progress; mark ready here because SET_INTERFACE
                    # (which triggers open_itf_cb) is optional and macOS skips it.
                    self._ready = True
                    return _REPORT_DESC
                if (bm & 0x60) == 0x20 and wi == self._itf:
                    return True
            return True

        def _open_itf_cb(desc=None):
            if desc is None or len(desc) < 6:
                self._ready = True
                return
            if desc[1] == 0x04 and desc[2] == self._itf:
                self._ready = True

        def _reset_cb(*_args):
            self._ready = False
            self._xfer_busy = False

        def _xfer_cb(*_args):
            self._xfer_busy = False

        # IMPORTANT: When MicroPython boots, the built-in CDC driver is
        # already active and the host has already enumerated us as a CDC
        # device for the REPL. Just rewriting the config and calling
        # active(True) is a no-op for the host — it still thinks we're CDC.
        # We must explicitly disconnect (active(False) -> tud_disconnect())
        # and pause long enough for the host to register the disconnect,
        # then reconnect with the new descriptors. macOS in particular
        # caches enumeration state aggressively; without a real disconnect
        # it never re-reads the descriptors and the HID interface is
        # invisible.
        try:
            self._dev.active(False)
        except OSError:
            pass
        sleep_ms_blocking(150)
        self._dev.builtin_driver = self._builtin_driver
        self._dev.config(
            desc_dev,
            desc_cfg,
            desc_strs=desc_strs,
            control_xfer_cb=_control_cb,
            open_itf_cb=_open_itf_cb,
            reset_cb=_reset_cb,
            xfer_cb=_xfer_cb,
        )
        self._dev.active(True)

    def is_open(self) -> bool:
        return self._ready

    async def wait_open(self, timeout_ms: int = 5000) -> bool:
        """Wait until the host has enumerated the HID interface, or timeout."""
        elapsed = 0
        step = 50
        while not self._ready and elapsed < timeout_ms:
            await sleep_ms(step)
            elapsed += step
        return self._ready

    def stats(self) -> tuple[int, int]:
        """Return (total_submits, failed_submits) — useful for diagnostics."""
        return self._submit_total, self._submit_failures

    async def press(self, *keycodes: int) -> None:
        modifier = self._held_modifiers
        keys = list(self._held_keys)
        for keycode in keycodes:
            if 0xE0 <= keycode <= 0xE7:
                modifier |= 1 << (keycode - 0xE0)
            elif keycode and keycode not in keys and len(keys) < 6:
                keys.append(keycode)
        await self._write_report(modifier, keys)

    async def hold(self, *keycodes: int) -> None:
        for keycode in keycodes:
            if 0xE0 <= keycode <= 0xE7:
                self._held_modifiers |= 1 << (keycode - 0xE0)
            elif keycode and keycode not in self._held_keys and len(self._held_keys) < 6:
                self._held_keys.append(keycode)
        await self.send_held_state()

    async def release(self, *keycodes: int) -> None:
        if not keycodes:
            await self.release_all()
            return
        for keycode in keycodes:
            if 0xE0 <= keycode <= 0xE7:
                self._held_modifiers &= ~(1 << (keycode - 0xE0))
            elif keycode in self._held_keys:
                self._held_keys.remove(keycode)
        await self.send_held_state()

    async def send_held_state(self) -> None:
        await self._write_report(self._held_modifiers, self._held_keys)

    async def release_all(self) -> None:
        self._held_modifiers = 0
        self._held_keys = []
        await self._write_report(0, [])

    async def _write_report(self, modifier: int, keys: list[int]) -> None:
        self._report[0] = modifier
        self._report[1] = 0
        for i in range(6):
            self._report[2 + i] = keys[i] if i < len(keys) else 0
        await self._send()

    async def _send(self) -> None:
        self._submit_total += 1
        if not self._ready:
            await self.wait_open(2000)

        elapsed = 0
        while self._xfer_busy and elapsed < 50:
            await sleep_ms(2)
            elapsed += 2

        for _ in range(10):
            try:
                self._xfer_busy = True
                self._dev.submit_xfer(self._ep_in, self._report)
                break
            except OSError:
                self._xfer_busy = False
                await sleep_ms(3)
        else:
            self._submit_failures += 1
            return

        elapsed = 0
        while self._xfer_busy and elapsed < 50:
            await sleep_ms(2)
            elapsed += 2


def _mod_to_keycodes(modifier):
    result = []
    if modifier & 0x01:
        result.append(_MOD_LEFT_CTRL)
    if modifier & 0x02:
        result.append(_MOD_LEFT_SHIFT)
    if modifier & 0x04:
        result.append(_MOD_LEFT_ALT)
    if modifier & 0x08:
        result.append(_MOD_LEFT_GUI)
    if modifier & 0x10:
        result.append(_MOD_RIGHT_CTRL)
    if modifier & 0x20:
        result.append(_MOD_RIGHT_SHIFT)
    if modifier & 0x40:
        result.append(_MOD_RIGHT_ALT)
    if modifier & 0x80:
        result.append(_MOD_RIGHT_GUI)
    return result


async def send_keys(kbd, modifier, keycodes) -> None:
    pressed = [kc for kc in keycodes if kc]
    if not pressed and not modifier:
        return
    await kbd.press(*_mod_to_keycodes(modifier), *pressed)
    await sleep_ms(20)
    await kbd.send_held_state()
    await sleep_ms(20)


async def hold_keys(kbd, modifier, keycodes) -> None:
    await kbd.hold(*_mod_to_keycodes(modifier), *[kc for kc in keycodes if kc])


async def release_keys(kbd, modifier, keycodes) -> None:
    if not modifier and not keycodes:
        await kbd.release_all()
        return
    await kbd.release(*_mod_to_keycodes(modifier), *[kc for kc in keycodes if kc])


async def send_key(kbd, modifier, keycode) -> None:
    await send_keys(kbd, modifier, [keycode] if keycode else [])


async def type_string(kbd, text, char_delay_ms=0, layout_code=DEFAULT_LAYOUT_CODE) -> None:
    for ch in text:
        steps = lookup_char_steps(ch, layout_code)
        for modifier, keycode in steps:
            await send_key(kbd, modifier, keycode)
            if char_delay_ms > 0:
                await sleep_ms(char_delay_ms)
