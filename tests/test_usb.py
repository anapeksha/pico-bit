import keyboard
from usb import (
    USB_AGENT_UNIX_NAME,
    USB_AGENT_WINDOWS_NAME,
    USBService,
    initialize_usb,
    usb_agent_filename,
    usb_initialized,
    usb_runtime_active,
)


def test_usb_agent_filename_is_platform_specific() -> None:
    assert usb_agent_filename('windows') == USB_AGENT_WINDOWS_NAME
    assert usb_agent_filename('linux') == USB_AGENT_UNIX_NAME
    assert usb_agent_filename('macos') == USB_AGENT_UNIX_NAME


def test_usb_service_state_transitions_with_available_adapter(tmp_path) -> None:
    agent = tmp_path / 'payload.bin'
    agent.write_bytes(b'\x7fELFtest')
    drive = USBService()
    drive._available = True
    drive._unavailable_reason = ''

    mounted = drive.set_mounted(True, agent_path=str(agent))
    unmounted = drive.set_mounted(False, agent_path=str(agent))

    assert mounted['mounted'] is True
    assert mounted['active'] is True
    assert mounted['state'] == 'active'
    assert unmounted['mounted'] is False
    assert unmounted['state'] == 'inactive'


def test_usb_service_mounts_even_without_agent(tmp_path) -> None:
    drive = USBService()
    drive._available = True
    drive._unavailable_reason = ''

    state = drive.set_mounted(True, agent_path=str(tmp_path / 'missing.bin'))

    assert state['mounted'] is True
    assert state['state'] == 'active'


def test_usb_and_keyboard_initializers_share_runtime_state() -> None:
    assert usb_initialized() is False
    assert keyboard.keyboard_initialized() is False

    initialize_usb()
    kbd = keyboard.initialize_keyboard()

    assert usb_initialized() is True
    assert keyboard.keyboard_initialized() is True
    assert kbd is keyboard.get_keyboard()
    assert usb_runtime_active() is True


class _BuiltinMscDriver:
    itf_max = 1
    ep_max = 2
    str_max = 3
    desc_dev = b'\x12\x01'
    desc_cfg = bytes(
        [
            9,
            2,
            32,
            0,
            1,
            1,
            0,
            0x80,
            50,
            9,
            4,
            0,
            0,
            2,
            0x08,
            0x06,
            0x50,
            0,
        ]
    )


class _DefaultMscDevice:
    BUILTIN_DEFAULT = _BuiltinMscDriver()


class _ExplicitMscDevice:
    BUILTIN_MSC = _BuiltinMscDriver()


def test_usb_service_detects_msc_from_builtin_default_descriptor() -> None:
    drive = USBService()
    drive._device = _DefaultMscDevice()  # type: ignore[assignment]

    assert drive.msc_supported() is True
    assert drive.builtin_msc_driver() is _DefaultMscDevice.BUILTIN_DEFAULT


def test_usb_service_accepts_explicit_builtin_msc_driver() -> None:
    drive = USBService()
    drive._device = _ExplicitMscDevice()  # type: ignore[assignment]

    assert drive.msc_supported() is True
    assert drive.builtin_msc_driver() is _ExplicitMscDevice.BUILTIN_MSC


class _RuntimeWithLazyOpen:
    def __init__(self) -> None:
        self.active = False

    def set_active(self, active: bool) -> None:
        self.active = active

    def is_open(self) -> bool:
        return False


def test_usb_service_reports_active_after_runtime_is_bound() -> None:
    drive = USBService()
    drive._available = True
    runtime = _RuntimeWithLazyOpen()

    drive.bind_runtime(runtime)

    assert drive.runtime_active() is True
    assert drive.state()['state'] == 'active'
