"""Frozen firmware entrypoint.

Importing ``main`` starts the runtime via its module-level bootstrap.
"""

# ruff: noqa: E402

from keyboard import initialize_keyboard
from usb import initialize_usb

# Configure the composite USB device as early as possible so the runtime
# `machine.USBDevice` state matches the host-visible MSC+HID device.
initialize_usb()
initialize_keyboard()

import main  # noqa: F401
