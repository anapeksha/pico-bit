"""
Build-time configurable runtime settings for the bundled Pico image.

These defaults are used during local development and when ``build.py`` is run
without overrides. The bundler can replace them in the emitted ``dist/boot.py``
so contributors do not need to edit source files just to change deployment
settings for a board.
"""

from ducky.constants import EDUCATIONAL_MODE_DEFAULT

AP_SSID: str = 'picoBit'
AP_PASSWORD: str = '88888888'
EDUCATIONAL_MODE: bool = EDUCATIONAL_MODE_DEFAULT
