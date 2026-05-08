from ducky.analysis import analyze_script


def test_analyze_script_reports_parsed_commands_for_valid_payload() -> None:
    result = analyze_script('STRING hello\nDELAY 50\n')

    assert result['blocking'] is False
    assert result['can_save'] is True
    assert result['command_count'] == 2
    assert result['parsed_commands'] == [
        {
            'depth': 0,
            'detail': 'hello',
            'kind': 'string',
            'label': 'STRING',
            'line': 1,
        },
        {
            'depth': 0,
            'detail': '50',
            'kind': 'command',
            'label': 'DELAY',
            'line': 2,
        },
    ]


def test_analyze_script_parses_formerly_unsafe_commands_without_errors() -> None:
    result = analyze_script('WAIT_FOR_CAPS_ON\n')

    assert result['blocking'] is False
    assert result['error_count'] == 0
    assert result['command_count'] == 1


def test_analyze_script_reports_parse_errors_with_hint() -> None:
    result = analyze_script('IF TRUE\nSTRING hi\n')

    assert result['blocking'] is True
    assert result['parsed_commands'] == []
    assert result['diagnostics'][0]['code'] == 'parse_error'
    assert result['diagnostics'][0]['line'] == 1
    assert 'Close the current block' in result['diagnostics'][0]['hint']


def test_analyze_script_warns_when_rd_kbd_is_used() -> None:
    result = analyze_script('RD_KBD WIN DE\nSTRING hi\n')

    assert result['blocking'] is False
    assert result['warning_count'] == 1
    assert result['diagnostics'][0]['code'] == 'layout_managed'
    assert 'portal' in result['diagnostics'][0]['message'].lower()
