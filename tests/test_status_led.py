import status_led


def test_status_led_patterns_include_expected_codes() -> None:
    assert isinstance(status_led.STATUS_LED, status_led.StatusLed)
    assert 'boot' in status_led.STAGE_PATTERNS
    assert 'payload_running' in status_led.STAGE_PATTERNS
    assert 'safe_mode_changed' in status_led.STAGE_PATTERNS
    assert 'keyboard_layout_changed' in status_led.STAGE_PATTERNS
    assert 'setup_entered' in status_led.STAGE_PATTERNS
    assert 'usb_enum_timeout' in status_led.ERROR_PATTERNS
    assert 'setup_ap_failed' in status_led.ERROR_PATTERNS
