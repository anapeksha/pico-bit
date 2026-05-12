import sys

from .api import auth as _auth

sys.modules[__name__] = _auth
