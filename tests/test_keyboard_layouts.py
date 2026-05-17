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
    win_codes = [item['code'] for item in supported_layouts('WIN')]
    mac_codes = [item['code'] for item in supported_layouts('MAC')]
    lnx_codes = [item['code'] for item in supported_layouts('LNX')]
    assert win_codes == [
        'US', 'UK', 'DE', 'FR', 'ES', 'IT',
        'SE', 'NO', 'DK', 'FI', 'PL', 'CZ', 'HU',
        'ES_LATAM', 'PT_BR', 'JP', 'RU', 'KR',
    ]
    assert lnx_codes == win_codes
    # macOS has all but UK and IT (which historically aliased to WIN).
    assert mac_codes == [
        'US', 'FR', 'SE', 'NO', 'DK', 'FI', 'PL', 'CZ', 'HU',
        'ES_LATAM', 'PT_BR', 'JP', 'RU', 'KR',
    ]


def test_mac_french_layout_uses_platform_specific_mapping() -> None:
    assert lookup_char_steps('[', 'MAC_FR') == [(MOD_ALTGR | MOD_SHIFT, 0x2E)]


def test_linux_profiles_split_into_platform_and_layout_codes() -> None:
    assert split_layout_code('LNX_DE') == ('LNX', 'DE')


# --- New layouts: shell-critical ASCII positions + one accented sample each ---

def test_swedish_layout_pipe_uses_altgr_iso_key() -> None:
    # On Swedish ISO, `|` is AltGr+`<` (the non-US-ISO key, HID 0x64).
    assert lookup_char_steps('|', 'WIN_SE') == [(MOD_ALTGR, 0x64)]


def test_swedish_layout_at_sign_uses_altgr_two() -> None:
    assert lookup_char_steps('@', 'WIN_SE') == [(MOD_ALTGR, 0x1F)]


def test_swedish_layout_aring_is_direct_key() -> None:
    # å sits on the key right of P (HID 0x2F).
    assert lookup_char_steps('å', 'WIN_SE') == [(MOD_NONE, 0x2F)]


def test_norwegian_layout_swaps_ae_and_oe_vs_danish() -> None:
    # Norwegian places Ø on the ; key (HID 0x33) and Æ on the ' key (HID 0x34).
    # Danish is the opposite. Together these confirm the swap is in place.
    assert lookup_char_steps('ø', 'WIN_NO') == [(MOD_NONE, 0x33)]
    assert lookup_char_steps('æ', 'WIN_NO') == [(MOD_NONE, 0x34)]
    assert lookup_char_steps('ø', 'WIN_DK') == [(MOD_NONE, 0x34)]
    assert lookup_char_steps('æ', 'WIN_DK') == [(MOD_NONE, 0x33)]


def test_danish_layout_pipe_uses_altgr_plus_key() -> None:
    # Danish puts `|` on AltGr+`+` (HID 0x2e), not on the ISO key like Swedish.
    # Norwegian matches Danish here (since both derive from the same base).
    assert lookup_char_steps('|', 'WIN_DK') == [(MOD_ALTGR, 0x2E)]
    assert lookup_char_steps('|', 'WIN_NO') == [(MOD_ALTGR, 0x2E)]


def test_finnish_aliases_to_swedish() -> None:
    # Finnish ISO is physically identical to Swedish — alias must give the
    # same scancodes for every char tested.
    for ch in ('å', '|', '@', 'ö', 'ä'):
        assert lookup_char_steps(ch, 'WIN_FI') == lookup_char_steps(ch, 'WIN_SE')


def test_polish_programmer_layout_uses_us_ascii_positions() -> None:
    # Polish Programmer keeps US ASCII positions — `@`, `|`, `\` are typed
    # exactly as on a US keyboard. This is what makes the layout useful for
    # red-team payloads on Polish targets.
    assert lookup_char_steps('@', 'WIN_PL') == [(MOD_SHIFT, 0x1F)]
    assert lookup_char_steps('|', 'WIN_PL') == [(MOD_SHIFT, 0x31)]
    assert lookup_char_steps('\\', 'WIN_PL') == [(MOD_NONE, 0x31)]


def test_polish_programmer_layout_uses_altgr_for_polish_letters() -> None:
    assert lookup_char_steps('ą', 'WIN_PL') == [(MOD_ALTGR, 0x04)]
    assert lookup_char_steps('ł', 'WIN_PL') == [(MOD_ALTGR, 0x0F)]
    assert lookup_char_steps('ż', 'WIN_PL') == [(MOD_ALTGR, 0x1D)]
    # Uppercase combines Shift + AltGr.
    assert lookup_char_steps('Ł', 'WIN_PL') == [(MOD_ALTGR | MOD_SHIFT, 0x0F)]


def test_czech_qwertz_layout_top_row_replaces_digits_with_accents() -> None:
    # Czech QWERTZ puts the top digit row's unshifted positions over accented
    # letters: '3' shifted gives 3, unshifted gives š.
    assert lookup_char_steps('š', 'WIN_CZ') == [(MOD_NONE, 0x20)]


def test_hungarian_layout_uses_altgr_for_at_sign() -> None:
    # Hungarian's @ is AltGr+v on QWERTZ.
    assert lookup_char_steps('@', 'WIN_HU') == [(MOD_ALTGR, 0x19)]


def test_portuguese_br_abnt2_layout_has_cedilla_as_own_key() -> None:
    # On ABNT2 the cedilla key sits between L and the apostrophe.
    assert lookup_char_steps('ç', 'WIN_PT_BR') == [(MOD_NONE, 0x33)]


def test_es_latam_aliases_to_spanish() -> None:
    # Phase-1 alias — LATAM variant carries the same scancode positions as
    # Spain ES for shell-critical ASCII typing.
    for ch in ('@', '|', 'ñ', '?'):
        assert lookup_char_steps(ch, 'WIN_ES_LATAM') == lookup_char_steps(ch, 'WIN_ES')


def test_jp_ru_kr_stubs_alias_to_us_ascii() -> None:
    # Tier 2/3 stubs route through WIN_US for the ASCII subset DuckyScript
    # uses. Verify that critical shell chars match US output exactly.
    for layout in ('WIN_JP', 'WIN_RU', 'WIN_KR'):
        for ch in ('@', '|', '\\', '$', '/', '"', "'"):
            assert lookup_char_steps(ch, layout) == lookup_char_steps(ch, 'WIN_US'), (
                f'{layout} {ch!r} diverges from WIN_US'
            )


def test_lnx_aliases_match_their_win_sources() -> None:
    # Linux variants of the new layouts must produce identical scancodes to
    # their Windows sources (X11/Wayland use the same per-layout keycode tables).
    for suffix in ('SE', 'NO', 'DK', 'FI', 'PL', 'CZ', 'HU', 'PT_BR'):
        for ch in ('|', '\\', '@', '$'):
            assert lookup_char_steps(ch, f'LNX_{suffix}') == \
                lookup_char_steps(ch, f'WIN_{suffix}')
