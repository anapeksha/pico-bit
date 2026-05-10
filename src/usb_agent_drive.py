"""USB agent-drive state and capability adapter.

Release UF2 builds enable MicroPython's built-in USB-MSC driver and append the
runtime HID interface in ``hid.py``. This adapter owns only the portal-facing
state machine: stock/local MicroPython builds without built-in MSC remain
unavailable, while release firmware can arm the visible USB drive delivery path.
"""

import os

AGENT_VOLUME_LABEL = 'PICOBIT'
USB_AGENT_WINDOWS_NAME = 'pico-agent'
USB_AGENT_UNIX_NAME = 'pico-agent'


def usb_agent_filename(target_os: str) -> str:
    return USB_AGENT_WINDOWS_NAME if target_os == 'windows' else USB_AGENT_UNIX_NAME


class UsbAgentDrive:
    def __init__(self) -> None:
        self._mounted = False
        self._state = 'inactive'
        self._message = 'USB agent drive is inactive.'
        self._available, self._unavailable_reason = self._detect_capability()

    def _detect_capability(self) -> tuple[bool, str]:
        try:
            import machine  # type: ignore
        except (ImportError, AttributeError):
            return False, 'MicroPython runtime does not expose machine.USBDevice.'

        usb_device_type = getattr(machine, 'USBDevice', None)
        if usb_device_type is None:
            return False, 'MicroPython runtime does not expose machine.USBDevice.'

        try:
            dev = usb_device_type()
        except Exception:
            return False, 'MicroPython USBDevice is present but could not be initialized.'

        if getattr(dev, 'BUILTIN_MSC', None) is not None:
            return True, ''
        if getattr(dev, 'BUILTIN_CDC_MSC', None) is not None:
            return True, ''

        return False, 'Firmware was built without USB mass-storage support.'

    def state(self) -> dict[str, object]:
        if not self._available:
            state = 'unavailable'
            message = self._unavailable_reason
        else:
            state = self._state
            message = self._message
        return {
            'available': self._available,
            'can_mount': self._available and not self._mounted,
            'filename': USB_AGENT_UNIX_NAME,
            'mounted': self._mounted,
            'state': state,
            'volume_label': AGENT_VOLUME_LABEL,
            'message': message,
        }

    def set_mounted(self, mounted: bool, *, agent_path: str) -> dict[str, object]:
        if not self._available:
            return self.state()

        if mounted:
            try:
                os.stat(agent_path)
            except OSError:
                self._mounted = False
                self._state = 'error'
                self._message = 'Upload an agent binary before mounting the USB drive.'
                return self.state()

            self._mounted = True
            self._state = 'mounted'
            self._message = 'USB agent drive is armed.'
            return self.state()

        self._mounted = False
        self._state = 'inactive'
        self._message = 'USB agent drive is inactive.'
        return self.state()
