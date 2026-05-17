"""USB HID keyboard helpers for MicroPython on the Raspberry Pi Pico 2."""

from helpers import sleep_ms, sleep_ms_blocking
from usb import USB

# ruff: noqa: E501

LayoutData = dict

DEFAULT_PLATFORM_CODE = 'WIN'
DEFAULT_LAYOUT = 'US'
DEFAULT_LAYOUT_CODE = 'WIN_US'
MOD_NONE = 0x00
MOD_CTRL = 0x01
MOD_SHIFT = 0x02
MOD_ALT = 0x04
MOD_GUI = 0x08
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
    'SE': 'Swedish (SE)',
    'NO': 'Norwegian (NO)',
    'DK': 'Danish (DK)',
    'FI': 'Finnish (FI)',
    'PL': 'Polish (PL, Programmer)',
    'CZ': 'Czech (CZ)',
    'HU': 'Hungarian (HU)',
    'ES_LATAM': 'Spanish (LATAM)',
    'PT_BR': 'Portuguese (BR)',
    'JP': 'Japanese (JP, ASCII)',
    'RU': 'Russian (RU, Latin)',
    'KR': 'Korean (KR, ASCII)',
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
    'WIN_SE': {
        'label': 'Swedish (SE)',
        'ascii': b"\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\x9f\xa0!\xa2\xa31\xa5\xa6\xb1-687\xa4'\x1e\x1f !\"#$%&\xb7\xb6d\xa7\xe4\xad\x1f\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d%-&\x00\xb8\x00\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d$d'\x00L",
        'need_altgr': '$@[\\]{|}£µ€',
        'higher': {
            163: 32,
            164: 161,
            167: 53,
            181: 16,
            189: 181,
            196: 180,
            197: 175,
            214: 179,
            228: 52,
            229: 47,
            246: 51,
            8364: 34,
        },
        'combined': {
            94: 45088,
            96: 44576,
            126: 12448,
            168: 12320,
            180: 11808,
            192: 44609,
            193: 11841,
            194: 45121,
            195: 12481,
            196: 12353,
            200: 44613,
            201: 11845,
            202: 45125,
            203: 12357,
            204: 44617,
            205: 11849,
            206: 45129,
            207: 12361,
            209: 12494,
            210: 44623,
            211: 11855,
            212: 45135,
            213: 12495,
            214: 12367,
            217: 44629,
            218: 11861,
            219: 45141,
            220: 12373,
            221: 11865,
            224: 44641,
            225: 11873,
            226: 45153,
            227: 12513,
            228: 12385,
            232: 44645,
            233: 11877,
            234: 45157,
            235: 12389,
            236: 44649,
            237: 11881,
            238: 45161,
            239: 12393,
            241: 12526,
            242: 44655,
            243: 11887,
            244: 45167,
            245: 12527,
            246: 12399,
            249: 44661,
            250: 11893,
            251: 45173,
            252: 12405,
            253: 11897,
            255: 12409,
        },
    },
    'WIN_NO': {
        'label': 'Norwegian (NO)',
        'ascii': b"\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\x9f\xa0!\xa2\xa31\xa5\xa6\xb1-687\xa4'\x1e\x1f !\"#$%&\xb7\xb6d\xa7\xe4\xad\x1f\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d%d&\x00\xb8\x00\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d$.'\x00L",
        'need_altgr': '$@[\\]{|}£µ€',
        'higher': {
            163: 32,
            164: 161,
            167: 181,
            181: 16,
            189: 53,
            197: 175,
            198: 180,
            216: 179,
            229: 47,
            230: 52,
            248: 51,
            8364: 34,
        },
        'combined': {
            94: 45088,
            96: 44576,
            126: 12448,
            168: 12320,
            180: 11808,
            192: 44609,
            193: 11841,
            194: 45121,
            195: 12481,
            196: 12353,
            200: 44613,
            201: 11845,
            202: 45125,
            203: 12357,
            204: 44617,
            205: 11849,
            206: 45129,
            207: 12361,
            209: 12494,
            210: 44623,
            211: 11855,
            212: 45135,
            213: 12495,
            214: 12367,
            217: 44629,
            218: 11861,
            219: 45141,
            220: 12373,
            221: 11865,
            224: 44641,
            225: 11873,
            226: 45153,
            227: 12513,
            228: 12385,
            232: 44645,
            233: 11877,
            234: 45157,
            235: 12389,
            236: 44649,
            237: 11881,
            238: 45161,
            239: 12393,
            241: 12526,
            242: 44655,
            243: 11887,
            244: 45167,
            245: 12527,
            246: 12399,
            249: 44661,
            250: 11893,
            251: 45173,
            252: 12405,
            253: 11897,
            255: 12409,
        },
    },
    'WIN_DK': {
        'label': 'Danish (DK)',
        'ascii': b"\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\x9f\xa0!\xa2\xa31\xa5\xa6\xb1-687\xa4'\x1e\x1f !\"#$%&\xb7\xb6d\xa7\xe4\xad\x1f\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d%d&\x00\xb8\x00\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d$.'\x00L",
        'need_altgr': '$@[\\]{|}£µ€',
        'higher': {
            163: 32,
            164: 161,
            167: 181,
            181: 16,
            189: 53,
            197: 175,
            198: 179,
            216: 180,
            229: 47,
            230: 51,
            248: 52,
            8364: 34,
        },
        'combined': {
            94: 45088,
            96: 44576,
            126: 12448,
            168: 12320,
            180: 11808,
            192: 44609,
            193: 11841,
            194: 45121,
            195: 12481,
            196: 12353,
            200: 44613,
            201: 11845,
            202: 45125,
            203: 12357,
            204: 44617,
            205: 11849,
            206: 45129,
            207: 12361,
            209: 12494,
            210: 44623,
            211: 11855,
            212: 45135,
            213: 12495,
            214: 12367,
            217: 44629,
            218: 11861,
            219: 45141,
            220: 12373,
            221: 11865,
            224: 44641,
            225: 11873,
            226: 45153,
            227: 12513,
            228: 12385,
            232: 44645,
            233: 11877,
            234: 45157,
            235: 12389,
            236: 44649,
            237: 11881,
            238: 45161,
            239: 12393,
            241: 12526,
            242: 44655,
            243: 11887,
            244: 45167,
            245: 12527,
            246: 12399,
            249: 44661,
            250: 11893,
            251: 45173,
            252: 12405,
            253: 11897,
            255: 12409,
        },
    },
    # Polish Programmer (kbdpl1.dll) layout: ASCII keys identical to US,
    # AltGr layer adds the nine Polish accented letters. This is the default
    # Polish keyboard on Windows ("Polish Programmer") and the choice red-team
    # tooling overwhelmingly assumes (US-compatible shell command typing).
    'WIN_PL': {
        'label': 'Polish (PL, Programmer)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\xb4\xa0\xa1\xa2\xa44\xa6\xa7\xa5\xae6-78\'\x1e\x1f !"#$%&\xb33\xb6.\xb7\xb8\x9f\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d/10\xa3\xad5\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\xaf\xb1\xb0\xb5L',
        'need_altgr': 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ',
        'higher': {
            211: 0x92,  # Ó = Shift+AltGr+o
            243: 0x12,  # ó = AltGr+o
            260: 0x84,  # Ą = Shift+AltGr+a
            261: 0x04,  # ą = AltGr+a
            262: 0x86,  # Ć = Shift+AltGr+c
            263: 0x06,  # ć = AltGr+c
            280: 0x88,  # Ę = Shift+AltGr+e
            281: 0x08,  # ę = AltGr+e
            321: 0x8F,  # Ł = Shift+AltGr+l
            322: 0x0F,  # ł = AltGr+l
            323: 0x91,  # Ń = Shift+AltGr+n
            324: 0x11,  # ń = AltGr+n
            346: 0x96,  # Ś = Shift+AltGr+s
            347: 0x16,  # ś = AltGr+s
            377: 0x9B,  # Ź = Shift+AltGr+x
            378: 0x1B,  # ź = AltGr+x
            379: 0x9D,  # Ż = Shift+AltGr+z
            380: 0x1D,  # ż = AltGr+z
        },
        'combined': {},
    },
    'WIN_CZ': {
        'label': 'Czech (CZ)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\xb4\xb3\x1b3\xad\x06\xb1\xb008\x1e687\xaf\xa7\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xb756-7\xb6\x19\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9d\x9c\t\x14\n\x00\xb8\x00\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1d\x1c\x05\x1a\x11\x1eL',
        'need_altgr': '#$&*<>@[\\]{|}~¤×ß÷ĐđŁł€',
        'higher': {
            164: 49,
            167: 52,
            215: 48,
            223: 52,
            225: 37,
            233: 39,
            237: 38,
            247: 47,
            250: 47,
            253: 36,
            269: 33,
            272: 7,
            273: 22,
            283: 31,
            321: 15,
            322: 14,
            345: 34,
            353: 32,
            367: 51,
            382: 35,
            8364: 8,
        },
        'combined': {
            94: 8352,
            96: 9376,
            168: 11680,
            176: 8864,
            180: 9888,
            183: 9632,
            184: 11936,
            192: 9409,
            193: 9921,
            194: 8385,
            196: 11713,
            197: 8897,
            199: 11971,
            200: 9413,
            201: 9925,
            202: 8389,
            203: 11717,
            204: 9417,
            205: 9929,
            206: 8393,
            207: 11721,
            210: 9423,
            211: 9935,
            212: 8399,
            214: 11727,
            217: 9429,
            218: 9941,
            219: 8405,
            220: 11733,
            221: 9945,
            224: 9441,
            225: 9953,
            226: 8417,
            228: 11745,
            229: 8929,
            231: 12003,
            232: 9445,
            233: 9957,
            234: 8421,
            235: 11749,
            236: 9449,
            237: 9961,
            238: 8425,
            239: 11753,
            242: 9455,
            243: 9967,
            244: 8431,
            246: 11759,
            249: 9461,
            250: 9973,
            251: 8437,
            252: 11765,
            253: 9977,
            255: 11769,
            258: 8641,
            259: 8673,
            260: 9153,
            261: 9185,
            262: 9923,
            263: 9955,
            268: 8131,
            269: 8163,
            270: 8132,
            271: 8164,
            278: 9669,
            279: 9701,
            280: 9157,
            281: 9189,
            282: 8133,
            283: 8165,
            286: 8647,
            287: 8679,
            290: 11975,
            291: 12007,
            302: 9161,
            303: 9193,
            304: 9673,
            305: 9705,
            310: 11979,
            311: 12011,
            313: 9932,
            314: 9964,
            315: 11980,
            316: 12012,
            317: 8140,
            318: 8172,
            323: 9934,
            324: 9966,
            325: 11982,
            326: 12014,
            327: 8142,
            328: 8174,
            336: 10191,
            337: 10223,
            340: 9938,
            341: 9970,
            342: 11986,
            343: 12018,
            344: 8146,
            345: 8178,
            346: 9939,
            347: 9971,
            350: 11987,
            351: 12019,
            352: 8147,
            353: 8179,
            354: 11988,
            355: 12020,
            356: 8148,
            357: 8180,
            366: 8917,
            367: 8949,
            368: 10197,
            369: 10229,
            370: 9173,
            371: 9205,
            376: 11737,
            377: 9946,
            378: 9978,
            379: 9690,
            380: 9722,
            381: 8154,
            382: 8186,
            711: 8096,
            728: 8608,
            731: 9120,
            733: 10144,
        },
    },
    'WIN_HU': {
        'label': 'Hungarian (HU)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\xa1\x9f\x1b3\xa2\x06\x9e\xa5\xa68\xa0687\xa35\x1e\x1f !"#$%&\xb76\x10\xa4\x1d\xb6\x19\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9d\x9c\t\x14\n\x00\xb8$\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1d\x1c\x05\x1a\x11\x1eL',
        'need_altgr': '#$&*;<>@[\\]`{|}~¤ÄÍ×ßäí÷ĐđŁł€',
        'higher': {
            164: 49,
            167: 181,
            193: 180,
            196: 8,
            201: 179,
            205: 12,
            211: 174,
            214: 167,
            215: 48,
            218: 176,
            220: 173,
            223: 52,
            225: 52,
            228: 4,
            233: 51,
            237: 13,
            243: 46,
            246: 39,
            247: 47,
            250: 48,
            252: 45,
            272: 7,
            273: 22,
            321: 15,
            322: 14,
            336: 175,
            337: 47,
            368: 177,
            369: 49,
            8364: 24,
        },
        'combined': {
            94: 8352,
            168: 11680,
            176: 8864,
            180: 9888,
            184: 11936,
            193: 9921,
            194: 8385,
            196: 11713,
            199: 11971,
            201: 9925,
            203: 11717,
            205: 9929,
            206: 8393,
            211: 9935,
            212: 8399,
            214: 11727,
            218: 9941,
            220: 11733,
            221: 9945,
            225: 9953,
            226: 8417,
            228: 11745,
            231: 12003,
            233: 9957,
            235: 11749,
            237: 9961,
            238: 8425,
            243: 9967,
            244: 8431,
            246: 11759,
            250: 9973,
            252: 11765,
            253: 9977,
            258: 8641,
            259: 8673,
            260: 9153,
            261: 9185,
            262: 9923,
            263: 9955,
            268: 8131,
            269: 8163,
            270: 8132,
            271: 8164,
            280: 9157,
            281: 9189,
            282: 8133,
            283: 8165,
            313: 9932,
            314: 9964,
            323: 9934,
            324: 9966,
            327: 8142,
            328: 8174,
            336: 10191,
            337: 10223,
            340: 9938,
            341: 9970,
            344: 8146,
            345: 8178,
            346: 9939,
            347: 9971,
            350: 11987,
            351: 12019,
            352: 8147,
            353: 8179,
            354: 11988,
            355: 12020,
            356: 8148,
            357: 8180,
            366: 8917,
            367: 8949,
            368: 10197,
            369: 10229,
            377: 9946,
            378: 9978,
            379: 9690,
            380: 9722,
            381: 8154,
            382: 8186,
            711: 8096,
            728: 8608,
            729: 9632,
            731: 9120,
            733: 10144,
        },
    },
    'WIN_PT_BR': {
        'label': 'Portuguese (BR)',
        'ascii': b'\x00\x00\x00\x00\x00\x00\x00\x00*+(\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00)\x00\x00\x00\x00,\x9e\xb5\xa0\xa1\xa2\xa45\xa6\xa7\xa5\xae6-7\x14\'\x1e\x1f !"#$%&\xb88\xb6.\xb7\x1a\x9f\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d0d1\x00\xad\x00\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\xb0\xe4\xb1\x00L',
        'need_altgr': '/?¢£§ª¬°²³¹º₢',
        'higher': {
            162: 34,
            163: 33,
            167: 46,
            170: 48,
            172: 35,
            176: 8,
            178: 31,
            179: 32,
            185: 30,
            186: 49,
            199: 179,
            231: 51,
            8354: 6,
        },
        'combined': {
            94: 46112,
            96: 44832,
            126: 13344,
            168: 41760,
            180: 12064,
            192: 44865,
            193: 12097,
            194: 46145,
            195: 13377,
            196: 41793,
            200: 44869,
            201: 12101,
            202: 46149,
            203: 41797,
            204: 44873,
            205: 12105,
            206: 46153,
            207: 41801,
            209: 13390,
            210: 44879,
            211: 12111,
            212: 46159,
            213: 13391,
            214: 41807,
            217: 44885,
            218: 12117,
            219: 46165,
            220: 41813,
            221: 12121,
            224: 44897,
            225: 12129,
            226: 46177,
            227: 13409,
            228: 41825,
            232: 44901,
            233: 12133,
            234: 46181,
            235: 41829,
            236: 44905,
            237: 12137,
            238: 46185,
            239: 41833,
            241: 13422,
            242: 44911,
            243: 12143,
            244: 46191,
            245: 13423,
            246: 41839,
            249: 44917,
            250: 12149,
            251: 46197,
            252: 41845,
            253: 12153,
            255: 41849,
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
    # Tier 1 Linux aliases (Linux X11/Wayland follow the same scancode→char
    # mapping as Windows for these layouts).
    'LNX_SE': 'WIN_SE',
    'LNX_NO': 'WIN_NO',
    'LNX_DK': 'WIN_DK',
    'LNX_PL': 'WIN_PL',
    'LNX_CZ': 'WIN_CZ',
    'LNX_HU': 'WIN_HU',
    'LNX_PT_BR': 'WIN_PT_BR',
    # Finnish keyboard is physically identical to Swedish ISO.
    'WIN_FI': 'WIN_SE',
    'LNX_FI': 'WIN_SE',
    # Spanish (LATAM) overlaps with Spanish (Spain) for shell-critical ASCII;
    # the differences (peso sign, some accent dead-key positions) are out of
    # scope for the initial roll-out. Tracked as Phase-2 follow-on.
    'WIN_ES_LATAM': 'WIN_ES',
    'LNX_ES_LATAM': 'WIN_ES',
    # Tier 2/3 stubs — JIS / Russian / Korean physical scancode layouts differ
    # from US in several positions, but for the ASCII subset typed by Ducky-
    # Script attack commands, mapping through the US table works on most
    # targets because the host OS already reinterprets scancodes per its
    # configured locale. Real native encodings are tracked as follow-on work
    # (JIS in particular needs ASCII repositioning; Cyrillic and Hangul
    # typing both require OS IME interaction and are explicitly out of scope).
    'WIN_JP': 'WIN_US',
    'LNX_JP': 'WIN_US',
    'WIN_RU': 'WIN_US',
    'LNX_RU': 'WIN_US',
    'WIN_KR': 'WIN_US',
    'LNX_KR': 'WIN_US',
    # macOS aliases. MAC_FR is the only entry with a distinct Mac layout in
    # the existing table; the new layouts ship aliased to their WIN_* sources
    # since macOS Nordic/Polish/etc. differ from Windows mostly in dead-key
    # Option-layer positions (not in shell-critical ASCII positions).
    # Per-layout MAC_* native variants are Phase-2 follow-on.
    'MAC_SE': 'WIN_SE',
    'MAC_NO': 'WIN_NO',
    'MAC_DK': 'WIN_DK',
    'MAC_FI': 'WIN_SE',
    'MAC_PL': 'WIN_PL',
    'MAC_CZ': 'WIN_CZ',
    'MAC_HU': 'WIN_HU',
    'MAC_ES_LATAM': 'WIN_ES',
    'MAC_PT_BR': 'WIN_PT_BR',
    'MAC_JP': 'WIN_US',
    'MAC_RU': 'WIN_US',
    'MAC_KR': 'WIN_US',
}

for _alias, _source in _ALIASES.items():
    _LAYOUTS[_alias] = dict(_LAYOUTS[_source])

_SUPPORTED_LAYOUTS = {
    'WIN': (
        'US',
        'UK',
        'DE',
        'FR',
        'ES',
        'IT',
        'SE',
        'NO',
        'DK',
        'FI',
        'PL',
        'CZ',
        'HU',
        'ES_LATAM',
        'PT_BR',
        'JP',
        'RU',
        'KR',
    ),
    'MAC': (
        'US',
        'FR',
        'SE',
        'NO',
        'DK',
        'FI',
        'PL',
        'CZ',
        'HU',
        'ES_LATAM',
        'PT_BR',
        'JP',
        'RU',
        'KR',
    ),
    'LNX': (
        'US',
        'UK',
        'DE',
        'FR',
        'ES',
        'IT',
        'SE',
        'NO',
        'DK',
        'FI',
        'PL',
        'CZ',
        'HU',
        'ES_LATAM',
        'PT_BR',
        'JP',
        'RU',
        'KR',
    ),
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


_layout_data_cache: tuple[str | None, LayoutData] | None = None


def _layout_data(code: str | None) -> LayoutData:
    global _layout_data_cache
    if _layout_data_cache is not None and _layout_data_cache[0] == code:
        return _layout_data_cache[1]
    normalized = normalize_layout_code(code)
    result = _LAYOUTS.get(normalized, _LAYOUTS[DEFAULT_LAYOUT_CODE])
    _layout_data_cache = (code, result)
    return result


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
        rest.insert(0, first)
        return rest

    return []


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

_KEYBOARD_SINGLETON = None

# Canonical HID Boot Keyboard descriptor — matches MicroPython's official
# usb.device.keyboard exactly (Logical/Usage Max = 101, the highest valid
# keycode in Usage Page 0x07). Earlier versions used 255 which required
# 16-bit encoding; macOS occasionally rejects nonstandard variants, so we
# match upstream byte-for-byte.
_REPORT_DESC = bytes(
    [
        0x05,
        0x01,
        0x09,
        0x06,
        0xA1,
        0x01,
        0x05,
        0x07,
        0x19,
        0xE0,
        0x29,
        0xE7,
        0x15,
        0x00,
        0x25,
        0x01,
        0x75,
        0x01,
        0x95,
        0x08,
        0x81,
        0x02,
        0x95,
        0x01,
        0x75,
        0x08,
        0x81,
        0x01,
        0x95,
        0x05,
        0x75,
        0x01,
        0x05,
        0x08,
        0x19,
        0x01,
        0x29,
        0x05,
        0x91,
        0x02,
        0x95,
        0x01,
        0x75,
        0x03,
        0x91,
        0x01,
        0x95,
        0x06,
        0x75,
        0x08,
        0x15,
        0x00,
        0x25,
        0x65,
        0x05,
        0x07,
        0x19,
        0x00,
        0x29,
        0x65,
        0x81,
        0x00,
        0xC0,
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


def _usb_config(dev):
    builtin = USB.builtin_msc_driver(dev)
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
        self._dev = USB.device()
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

        try:
            self._dev.active(False)
        except OSError:
            pass
        sleep_ms_blocking(150)
        self._dev.builtin_driver = self._builtin_driver  # type: ignore
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

    def set_active(self, active: bool) -> None:
        self._ready = False
        self._xfer_busy = False
        self._dev.active(active)

    def is_open(self) -> bool:
        return self._ready

    async def wait_open(self, timeout_ms: int = 5000) -> bool:
        elapsed = 0
        step = 50
        while not self._ready and elapsed < timeout_ms:
            await sleep_ms(step)
            elapsed += step
        return self._ready

    def stats(self) -> tuple[int, int]:
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
            await self.wait_open(5000)

        elapsed = 0
        while self._xfer_busy and elapsed < 150:
            await sleep_ms(2)
            elapsed += 2

        for _ in range(10):
            try:
                self._xfer_busy = True
                self._dev.submit_xfer(self._ep_in, self._report)
                break
            except Exception:  # noqa: BLE001
                self._xfer_busy = False
                await sleep_ms(3)
        else:
            self._submit_failures += 1
            return

        elapsed = 0
        while self._xfer_busy and elapsed < 150:
            await sleep_ms(2)
            elapsed += 2


def initialize_keyboard():
    global _KEYBOARD_SINGLETON
    USB.initialize()
    if _KEYBOARD_SINGLETON is None:
        _KEYBOARD_SINGLETON = HIDKeyboard()
    USB.bind_runtime(_KEYBOARD_SINGLETON)
    return _KEYBOARD_SINGLETON


def keyboard_initialized() -> bool:
    return _KEYBOARD_SINGLETON is not None


def get_keyboard():
    return initialize_keyboard()


def keyboard_ready() -> bool:
    return _KEYBOARD_SINGLETON is not None and _KEYBOARD_SINGLETON.is_open()


def reset_keyboard_for_tests() -> None:
    global _KEYBOARD_SINGLETON
    _KEYBOARD_SINGLETON = None


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
