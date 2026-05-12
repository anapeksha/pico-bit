"""Stateful USB runtime service for Pico Bit.

This module is the single source of truth for runtime USB state. It owns the
USBDevice handle, USB MSC capability checks, active/inactive control, and the
staged USB agent filename helpers used by the portal and binary injector.

MicroPython's official micropython-lib provides higher-level `usb.device.*`
helpers for HID, keyboard, CDC, MIDI, and mouse interfaces. Pico Bit keeps this
module as the USB source of truth because the project also needs built-in MSC
state, and micropython-lib does not currently provide an MSC package. Directly
importing `usb.device` would also collide with this module's top-level `usb`
name unless we vendored and rewrote the package namespace, which would add more
flash than it saves.
"""

import os

import machine

from helpers import sleep_ms_blocking

USB_AGENT_WINDOWS_NAME = 'payload.exe'
USB_AGENT_UNIX_NAME = 'payload.bin'
_USB_AGENT_FILES = (USB_AGENT_WINDOWS_NAME, USB_AGENT_UNIX_NAME)
_USB_UNAVAILABLE_REASON = 'Firmware was built without runtime USB MSC support.'
_USB_BACKEND = 'machine.USBDevice + built-in MSC'
_USB_BACKEND_NOTE = (
    'micropython-lib usb.device helpers are not used because this firmware needs '
    'built-in MSC and this module owns the top-level usb namespace.'
)


def _descriptor_has_msc_interface(desc_cfg) -> bool:
    try:
        desc = bytes(desc_cfg)
    except Exception:
        return False

    index = 0
    end = len(desc)
    while index + 1 < end:
        length = desc[index]
        descriptor_type = desc[index + 1]
        if length <= 0:
            break
        if descriptor_type == 0x04 and index + 5 < end and desc[index + 5] == 0x08:
            return True
        index += length
    return False


def _is_builtin_usb_driver(driver) -> bool:
    return (
        driver is not None
        and hasattr(driver, 'desc_dev')
        and hasattr(driver, 'desc_cfg')
        and hasattr(driver, 'itf_max')
        and hasattr(driver, 'ep_max')
        and hasattr(driver, 'str_max')
    )


def _is_builtin_msc_driver(driver) -> bool:
    return _is_builtin_usb_driver(driver) and _descriptor_has_msc_interface(driver.desc_cfg)


class USBService:
    def __init__(self) -> None:
        self._device = None
        self._runtime = None
        self._last_error: str = ''
        self._available: bool | None = None
        self._unavailable_reason: str = ''
        self._initialized: bool = False
        self._active_requested: bool = False

    def device(self):
        if self._device is None:
            self._device = machine.USBDevice()
        return self._device

    def builtin_msc_driver(self, dev=None):
        if dev is None:
            dev = self.device()
        for name in ('BUILTIN_MSC', 'BUILTIN_CDC_MSC'):
            driver = getattr(dev, name, None)
            if _is_builtin_usb_driver(driver):
                return driver
        default_driver = getattr(dev, 'BUILTIN_DEFAULT', None)
        if _is_builtin_msc_driver(default_driver):
            return default_driver
        return None

    def _detect_capability(self) -> tuple[bool, str]:
        if self._available is not None:
            return bool(self._available), self._unavailable_reason
        try:
            if self.builtin_msc_driver() is not None:
                self._available = True
                self._unavailable_reason = ''
                return True, ''
        except Exception:
            pass
        self._available = False
        self._unavailable_reason = _USB_UNAVAILABLE_REASON
        return False, _USB_UNAVAILABLE_REASON

    def initialize(self):
        self._detect_capability()
        self._initialized = True
        return self.device()

    def bind_runtime(self, runtime) -> None:
        self._runtime = runtime
        self._active_requested = True

    def initialized(self) -> bool:
        return self._initialized

    def msc_supported(self) -> bool:
        available, _reason = self._detect_capability()
        return available

    def runtime_active(self) -> bool:
        try:
            if self.device().active():
                return True
        except TypeError:
            pass
        except Exception:
            pass
        if self._active_requested and self._runtime is not None:
            return True
        try:
            return bool(self._runtime is not None and self._runtime.is_open())
        except Exception:
            return False

    def set_runtime_active(self, active: bool) -> bool:
        try:
            if self._runtime is not None:
                self._runtime.set_active(active)
            else:
                self.device().active(active)
            self._active_requested = active
        except Exception:
            return False
        return self.runtime_active() if active else not self.runtime_active()

    def refresh(self) -> bool:
        available, _reason = self._detect_capability()
        if not available:
            return False
        try:
            self.set_runtime_active(False)
            sleep_ms_blocking(120)
            return self.set_runtime_active(True)
        except Exception:
            return False

    def agent_filename(self, target_os: str) -> str:
        return USB_AGENT_WINDOWS_NAME if target_os == 'windows' else USB_AGENT_UNIX_NAME

    def staged_binary_path(self, target_os: str | None = None) -> str:
        names = (self.agent_filename(target_os),) if target_os is not None else _USB_AGENT_FILES
        for name in names:
            try:
                os.stat(name)
                return name
            except OSError:
                continue
        return ''

    def staged_binary_name(self, target_os: str | None = None) -> str:
        return self.staged_binary_path(target_os)

    def staged_binary_matches_target(self, target_os: str) -> bool:
        staged = self.staged_binary_path()
        return bool(staged) and staged == self.agent_filename(target_os)

    def state(self) -> dict[str, object]:
        available, unavailable_reason = self._detect_capability()
        active = available and self.runtime_active()
        filename = self.staged_binary_name()
        has_binary = bool(filename)

        if not available:
            state = 'unavailable'
            message = unavailable_reason
        elif self._last_error and not active:
            state = 'error'
            message = self._last_error
        elif active:
            state = 'active'
            message = 'USB injector is active.'
        else:
            state = 'inactive'
            message = 'USB injector is inactive.'

        if active and not has_binary:
            message += ' Upload a binary to inject.'

        return {
            'active': active,
            'available': available,
            'backend': _USB_BACKEND,
            'backend_note': _USB_BACKEND_NOTE,
            'can_mount': available and not active,
            'can_unmount': available and active,
            'filename': filename,
            'has_binary': has_binary,
            'message': message,
            'mounted': active,
            'state': state,
            'volume_label': '',
            'volume_note': 'Host volume names come from the filesystem and may appear as No Name.',
        }

    def set_mounted(self, mounted: bool, *, agent_path: str = '') -> dict[str, object]:
        del agent_path
        available, _reason = self._detect_capability()
        if not available:
            return self.state()

        try:
            ok = self.set_runtime_active(mounted)
            if not ok and mounted:
                self._last_error = 'USB injector could not be activated.'
            elif not ok:
                self._last_error = 'USB injector could not be deactivated.'
            else:
                self._last_error = ''
        except Exception as exc:
            self._last_error = 'USB injector toggle failed: ' + str(exc)

        return self.state()

    def reset_for_tests(self) -> None:
        self._device = None
        self._runtime = None
        self._last_error = ''
        self._available = None
        self._unavailable_reason = ''
        self._initialized = False
        self._active_requested = False
        try:
            machine.USBDevice().active(False)
        except Exception:
            pass


USB = USBService()


def initialize_usb():
    return USB.initialize()


def usb_initialized() -> bool:
    return USB.initialized()


def usb_msc_supported() -> bool:
    return USB.msc_supported()


def usb_runtime_active() -> bool:
    return USB.runtime_active()


def set_usb_runtime_active(active: bool) -> bool:
    return USB.set_runtime_active(active)


def usb_agent_filename(target_os: str) -> str:
    return USB.agent_filename(target_os)


def staged_binary_path(target_os: str | None = None) -> str:
    return USB.staged_binary_path(target_os)


def staged_binary_name(target_os: str | None = None) -> str:
    return USB.staged_binary_name(target_os)


def staged_binary_matches_target(target_os: str) -> bool:
    return USB.staged_binary_matches_target(target_os)
