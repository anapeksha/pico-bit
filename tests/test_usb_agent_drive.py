from usb_agent_drive import (
    USB_AGENT_UNIX_NAME,
    USB_AGENT_WINDOWS_NAME,
    UsbAgentDrive,
    usb_agent_filename,
)


def test_usb_agent_filename_is_platform_specific() -> None:
    assert usb_agent_filename('windows') == USB_AGENT_WINDOWS_NAME
    assert usb_agent_filename('linux') == USB_AGENT_UNIX_NAME
    assert usb_agent_filename('macos') == USB_AGENT_UNIX_NAME


def test_usb_agent_drive_state_transitions_with_available_adapter(tmp_path) -> None:
    agent = tmp_path / 'payload.bin'
    agent.write_bytes(b'\x7fELFtest')
    drive = UsbAgentDrive()
    drive._available = True
    drive._unavailable_reason = ''

    mounted = drive.set_mounted(True, agent_path=str(agent))
    unmounted = drive.set_mounted(False, agent_path=str(agent))

    assert mounted['mounted'] is True
    assert mounted['state'] == 'mounted'
    assert mounted['volume_label'] == 'PICOBIT'
    assert unmounted['mounted'] is False
    assert unmounted['state'] == 'inactive'


def test_usb_agent_drive_refuses_mount_without_agent(tmp_path) -> None:
    drive = UsbAgentDrive()
    drive._available = True
    drive._unavailable_reason = ''

    state = drive.set_mounted(True, agent_path=str(tmp_path / 'missing.bin'))

    assert state['mounted'] is False
    assert state['state'] == 'error'
    assert 'Upload an agent binary' in str(state['message'])
