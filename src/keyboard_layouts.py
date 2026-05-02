"""Compact keyboard layout tables for typed-text injection."""

# ruff: noqa: E501

LayoutData = dict


DEFAULT_PLATFORM_CODE = 'WIN'
DEFAULT_LAYOUT = 'US'
DEFAULT_LAYOUT_CODE = 'WIN_US'
MOD_NONE = 0x00
MOD_SHIFT = 0x02
MOD_ALTGR = 0x40
_SHIFT_FLAG = 0x80

_PLATFORM_LABELS = {
    'WIN': 'Windows',
    'MAC': 'macOS',
    'LNX': 'Linux',
}

_LAYOUT_LABELS = {
    'US': 'English (US)',
    'UK': 'English (UK)',
    'DE': 'German (DE)',
    'FR': 'French (FR)',
    'ES': 'Spanish (ES)',
    'IT': 'Italian (IT)',
}

_LAYOUTS = {
    'WIN_US': {
        'label': 'English (US)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\xb4\xa0\xa1\xa2\xa44\xa6\xa7\xa5\xae6-78\'\x1e\x1f !"#$%&\xb33\xb6.\xb7\xb8\x9f\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d/10\xa3\xad5\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\xaf\xb1\xb0\xb5L',
        'need_altgr': '',
        'higher': {},
        'combined': {},
    },
    'WIN_UK': {
        'label': 'English (UK)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\x9f1\xa1\xa2\xa44\xa6\xa7\xa5\xae6-78\'\x1e\x1f !"#$%&\xb33\xb6.\xb7\xb8\xb4\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d/10\xa3\xad5\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\xaf\xe4\xb0\xb1\x00',
        'need_altgr': '\\¦áéíóú€',
        'higher': {
            163: 160,
            8364: 33,
            233: 8,
            250: 24,
            237: 12,
            243: 18,
            225: 4,
            172: 181,
            166: 53,
        },
        'combined': {},
    },
    'WIN_DE': {
        'label': 'German (DE)',
        'ascii': b"\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\x9f1\xa1\xa2\xa3\xb1\xa5\xa6\xb00687\xa4'\x1e\x1f !\"#$%&\xb7\xb6d\xa7\xe4\xad\x14\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9d\x9c%-&\x00\xb8\x00\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1d\x1c$d'0\x00",
        'need_altgr': '@[\\]{|}~²³µ€',
        'higher': {
            178: 31,
            167: 160,
            179: 32,
            223: 45,
            8364: 8,
            252: 47,
            220: 175,
            246: 51,
            214: 179,
            228: 52,
            196: 180,
            176: 181,
            181: 16,
        },
        'combined': {
            225: 11873,
            233: 11877,
            237: 11881,
            243: 11887,
            250: 11893,
            253: 11897,
            193: 11841,
            201: 11845,
            205: 11849,
            211: 11855,
            218: 11861,
            221: 11865,
            180: 11808,
            224: 44641,
            232: 44645,
            236: 44649,
            242: 44655,
            249: 44661,
            192: 44609,
            200: 44613,
            204: 44617,
            210: 44623,
            217: 44629,
            96: 44576,
            226: 13665,
            234: 13669,
            238: 13673,
            244: 13679,
            251: 13685,
            194: 13633,
            202: 13637,
            206: 13641,
            212: 13647,
            219: 13653,
            94: 13600,
        },
    },
    'WIN_FR': {
        'label': 'French (FR)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,8  0\xb4\x1e!"-1\xae\x10#\xb6\xb7\xa7\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa676d.\xe4\x90\'\x94\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\xb3\x91\x92\x93\x84\x95\x96\x97\x98\x99\x9d\x9b\x9c\x9a"%-&%\x00\x14\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f3\x11\x12\x13\x04\x15\x16\x17\x18\x19\x1d\x1b\x1c\x1a!#.\x00\x00',
        'need_altgr': '#@[\\]^{|}¤€',
        'higher': {
            233: 31,
            232: 36,
            231: 38,
            224: 39,
            176: 173,
            8364: 8,
            163: 176,
            164: 48,
            249: 52,
            178: 53,
            181: 177,
            167: 184,
        },
        'combined': {
            227: 8161,
            195: 8129,
            241: 8174,
            209: 8142,
            245: 8175,
            213: 8143,
            126: 8096,
            224: 9441,
            232: 9445,
            236: 9449,
            242: 9455,
            249: 9461,
            192: 9409,
            200: 9413,
            204: 9417,
            210: 9423,
            217: 9429,
            96: 9376,
            226: 12129,
            234: 12133,
            238: 12137,
            244: 12143,
            251: 12149,
            194: 12097,
            202: 12101,
            206: 12105,
            212: 12111,
            219: 12117,
            94: 12064,
            228: 44897,
            235: 44901,
            239: 44905,
            246: 44911,
            252: 44917,
            255: 44921,
            196: 44865,
            203: 44869,
            207: 44873,
            214: 44879,
            220: 44885,
            168: 44832,
        },
    },
    'WIN_ES': {
        'label': 'Spanish (ES)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\x9f \xa1\xa2\xa3-\xa5\xa6\xb00687\xa4\'\x1e\x1f !"#$%&\xb7\xb6d\xa7\xe4\xad\x1f\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d/50\x00\xb8\x00\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d4\x1e1\x00\x00',
        'need_altgr': '#@[\\]{|}¬€',
        'higher': {
            183: 160,
            8364: 34,
            172: 35,
            161: 46,
            191: 174,
            241: 51,
            209: 179,
            186: 53,
            170: 181,
            231: 49,
            199: 177,
        },
        'combined': {
            227: 8673,
            241: 8686,
            245: 8687,
            195: 8641,
            209: 8654,
            213: 8655,
            126: 8608,
            224: 12129,
            232: 12133,
            236: 12137,
            242: 12143,
            249: 12149,
            192: 12097,
            200: 12101,
            204: 12105,
            210: 12111,
            217: 12117,
            96: 12064,
            226: 44897,
            234: 44901,
            238: 44905,
            244: 44911,
            251: 44917,
            194: 44865,
            202: 44869,
            206: 44873,
            212: 44879,
            219: 44885,
            94: 44832,
            225: 13409,
            233: 13413,
            237: 13417,
            243: 13423,
            250: 13429,
            253: 13433,
            193: 13377,
            201: 13381,
            205: 13385,
            211: 13391,
            218: 13397,
            221: 13401,
            180: 13344,
            228: 46177,
            235: 46181,
            239: 46185,
            246: 46191,
            252: 46197,
            255: 46201,
            196: 46145,
            203: 46149,
            207: 46153,
            214: 46159,
            220: 46165,
            168: 46112,
        },
    },
    'WIN_IT': {
        'label': 'Italian (IT)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\x9f4\xa1\xa2\xa3-\xa5\xa6\xb00687\xa4\'\x1e\x1f !"#$%&\xb7\xb6d\xa7\xe4\xad3\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d/50\xae\xb8\x00\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\xaf\xb5\xb0\x00\x00',
        'need_altgr': '#@[]€{}',
        'higher': {
            163: 160,
            8364: 34,
            236: 46,
            232: 47,
            233: 175,
            242: 51,
            231: 179,
            224: 52,
            176: 180,
            249: 49,
            167: 177,
        },
        'combined': {},
    },
    'MAC_FR': {
        'label': 'French (FR)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,% \xe40\xb4\x1e!\xb0\xb8\x10.-\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa67\x8658\xb5\x90d\x94\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\xb3\x91\x92\x93\x84\x95\x96\x97\x98\x99\x9d\x9b\x9c\x9a\xa2\xb7\xad\x00\xae\x00\x14\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f3\x11\x12\x13\x04\x15\x16\x17\x18\x19\x1d\x1b\x1c\x1a"\x8f-\x00\x00',
        'need_altgr': '[]\\{}|~€',
        'higher': {
            224: 39,
            231: 38,
            232: 36,
            233: 31,
            249: 52,
            8364: 48,
            176: 173,
            167: 35,
            163: 177,
        },
        'combined': {
            227: 4577,
            195: 4545,
            241: 4590,
            209: 4558,
            245: 4591,
            213: 4559,
            126: 4512,
            217: 12629,
            96: 12576,
            236: 12649,
            204: 12617,
            242: 12655,
            210: 12623,
            192: 12609,
            200: 12613,
            226: 12129,
            234: 12133,
            238: 12137,
            244: 12143,
            251: 12149,
            194: 12097,
            202: 12101,
            206: 12105,
            212: 12111,
            219: 12117,
            94: 12064,
            228: 44897,
            235: 44901,
            239: 44905,
            246: 44911,
            252: 44917,
            255: 44921,
            196: 44865,
            203: 44869,
            207: 44873,
            214: 44879,
            220: 44885,
            168: 44832,
        },
    },
}

_ALIASES = {
    'MAC_US': 'WIN_US',
    'LNX_US': 'WIN_US',
    'LNX_UK': 'WIN_UK',
    'LNX_DE': 'WIN_DE',
    'LNX_FR': 'WIN_FR',
    'LNX_ES': 'WIN_ES',
    'LNX_IT': 'WIN_IT',
}

for _alias, _source in _ALIASES.items():
    _LAYOUTS[_alias] = dict(_LAYOUTS[_source])

_SUPPORTED_LAYOUTS = {
    'WIN': ('US', 'UK', 'DE', 'FR', 'ES', 'IT'),
    'MAC': ('US', 'FR'),
    'LNX': ('US', 'UK', 'DE', 'FR', 'ES', 'IT'),
}


def _option(platform: str, layout: str) -> dict[str, str]:
    return {
        'code': f'{platform}_{layout}',
        'label': _LAYOUT_LABELS[layout],
        'layout': layout,
        'platform': platform,
        'platform_label': _PLATFORM_LABELS[platform],
    }


_OPTIONS = tuple(
    _option(platform, layout)
    for platform in ('WIN', 'MAC', 'LNX')
    for layout in _SUPPORTED_LAYOUTS[platform]
    if f'{platform}_{layout}' in _LAYOUTS
)
_OPTION_BY_CODE = {item['code']: item for item in _OPTIONS}


def normalize_platform_code(code: str | None) -> str:
    if not code:
        return DEFAULT_PLATFORM_CODE
    normalized = str(code).strip().upper().replace('-', '_').replace('/', '_')
    aliases = {
        'WINDOWS': 'WIN',
        'MACOS': 'MAC',
        'OSX': 'MAC',
        'LINUX': 'LNX',
    }
    return aliases.get(normalized, normalized)


def supported_platforms() -> list[dict[str, str]]:
    return [{'code': code, 'label': _PLATFORM_LABELS[code]} for code in ('WIN', 'MAC', 'LNX')]


def is_supported_platform(code: str | None) -> bool:
    if not code:
        return False
    return normalize_platform_code(code) in _SUPPORTED_LAYOUTS


def normalize_layout_name(code: str | None) -> str:
    if not code:
        return DEFAULT_LAYOUT
    normalized = str(code).strip().upper().replace('-', '_')
    if not normalized:
        return DEFAULT_LAYOUT
    if '_' in normalized:
        return normalized.split('_', 1)[1]
    return normalized


def default_layout_code(platform: str | None = None) -> str:
    normalized_platform = normalize_platform_code(platform)
    return f'{normalized_platform}_{DEFAULT_LAYOUT}'


def compose_layout_code(platform: str | None, layout: str | None) -> str:
    normalized_platform = normalize_platform_code(platform)
    normalized_layout = normalize_layout_name(layout)
    return f'{normalized_platform}_{normalized_layout}'


def normalize_layout_code(code: str | None, platform: str | None = None) -> str:
    if not code:
        return default_layout_code(platform)
    normalized = str(code).strip().upper().replace('-', '_')
    if not normalized:
        return default_layout_code(platform)
    if normalized in _LAYOUTS:
        return normalized
    if '_' in normalized:
        prefix, suffix = normalized.split('_', 1)
        return compose_layout_code(prefix, suffix)
    return compose_layout_code(platform, normalized)


def split_layout_code(code: str | None) -> tuple[str, str]:
    normalized = normalize_layout_code(code)
    platform, layout = normalized.split('_', 1)
    return platform, layout


def supported_layouts(platform: str | None = None) -> list[dict[str, str]]:
    if platform is None:
        return [dict(item) for item in _OPTIONS]
    normalized_platform = normalize_platform_code(platform)
    items: list[dict[str, str]] = []
    for layout in _SUPPORTED_LAYOUTS.get(
        normalized_platform, _SUPPORTED_LAYOUTS[DEFAULT_PLATFORM_CODE]
    ):
        code = f'{normalized_platform}_{layout}'
        if code not in _LAYOUTS:
            continue
        items.append({'code': layout, 'label': _LAYOUT_LABELS[layout]})
    return items


def is_supported_layout(code: str | None, platform: str | None = None) -> bool:
    if not code:
        return False
    return normalize_layout_code(code, platform) in _LAYOUTS


def layout_option(code: str | None) -> dict[str, str]:
    normalized = normalize_layout_code(code)
    option = _OPTION_BY_CODE.get(normalized)
    if option is not None:
        return dict(option)
    return dict(_OPTION_BY_CODE[DEFAULT_LAYOUT_CODE])


def layout_label(code: str | None) -> str:
    return layout_option(code)['label']


def _layout_data(code: str | None) -> LayoutData:
    normalized = normalize_layout_code(code)
    return _LAYOUTS.get(normalized, _LAYOUTS[DEFAULT_LAYOUT_CODE])


def _step(encoded: int, *, altgr: bool) -> tuple[int, int] | None:
    if not encoded:
        return None
    modifier = MOD_ALTGR if altgr else MOD_NONE
    keycode = encoded
    if keycode & _SHIFT_FLAG:
        modifier |= MOD_SHIFT
        keycode &= ~_SHIFT_FLAG
    return modifier, keycode


def lookup_char_steps(ch: str, layout_code: str | None = None) -> list[tuple[int, int]]:
    data = _layout_data(layout_code)
    need_altgr = str(data.get('need_altgr', ''))
    ascii_table = data.get('ascii', b'')
    higher = data.get('higher', {})
    combined = data.get('combined', {})
    char_ord = ord(ch)

    if not isinstance(ascii_table, bytes):
        ascii_table = b''
    if not isinstance(higher, dict):
        higher = {}
    if not isinstance(combined, dict):
        combined = {}

    if char_ord < len(ascii_table):
        step = _step(ascii_table[char_ord], altgr=ch in need_altgr)
        if step is not None:
            return [step]

    encoded = higher.get(char_ord, 0)
    if encoded:
        step = _step(encoded, altgr=ch in need_altgr)
        if step is not None:
            return [step]

    combined_encoded = combined.get(char_ord, 0)
    if combined_encoded:
        first = _step(combined_encoded >> 8, altgr=bool(combined_encoded & _SHIFT_FLAG))
        second = chr(combined_encoded & 0xFF & (~_SHIFT_FLAG))
        rest = lookup_char_steps(second, layout_code)
        if first is None:
            return rest
        return [first] + rest

    return []
