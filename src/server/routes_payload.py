import sys

from .api import payload as _payload

sys.modules[__name__] = _payload
