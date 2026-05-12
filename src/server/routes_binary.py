import sys

from .api import binary as _binary

sys.modules[__name__] = _binary
