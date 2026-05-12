import sys

from .api import usb_agent as _usb_agent

sys.modules[__name__] = _usb_agent
