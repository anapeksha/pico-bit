from keyboard import (
    MOD_ALTGR,
    MOD_NONE,
    MOD_SHIFT,
    lookup_char_steps,
    split_layout_code,
    supported_layouts,
    supported_platforms,
)


def test_us_layout_uses_shift_for_at_sign() -> None:
    assert lookup_char_steps('@', 'WIN_US') == [(MOD_SHIFT, 0x1F)]


def test_german_layout_uses_altgr_for_at_sign() -> None:
    assert lookup_char_steps('@', 'WIN_DE') == [(MOD_ALTGR, 0x14)]


def test_uk_layout_uses_non_us_backslash_key_for_pipe() -> None:
    assert lookup_char_steps('|', 'WIN_UK') == [(MOD_SHIFT, 0x64)]


def test_combined_character_returns_dead_key_sequence() -> None:
    assert lookup_char_steps('é', 'WIN_DE') == [(MOD_NONE, 0x2E), (MOD_NONE, 0x08)]


def test_supported_platforms_and_filtered_layouts_are_exposed() -> None:
    assert supported_platforms() == [
        {'code': 'WIN', 'label': 'Windows'},
        {'code': 'MAC', 'label': 'macOS'},
        {'code': 'LNX', 'label': 'Linux'},
    ]
    assert supported_layouts('MAC') == [
        {'code': 'US', 'label': 'English (US)'},
        {'code': 'FR', 'label': 'French (FR)'},
    ]


def test_mac_french_layout_uses_platform_specific_mapping() -> None:
    assert lookup_char_steps('[', 'MAC_FR') == [(MOD_ALTGR | MOD_SHIFT, 0x2E)]


def test_linux_profiles_split_into_platform_and_layout_codes() -> None:
    assert split_layout_code('LNX_DE') == ('LNX', 'DE')
