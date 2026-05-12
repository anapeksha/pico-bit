import sys

from .api import loot as _loot

sys.modules[__name__] = _loot
