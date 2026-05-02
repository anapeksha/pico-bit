from ducky.analysis import analyze_script


def test_analyze_script_reports_parsed_commands_for_valid_payload() -> None:
    result = analyze_script('STRING hello\nDELAY 50\n', allow_unsafe=False)

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


def test_analyze_script_blocks_unsafe_commands_in_safe_mode() -> None:
    result = analyze_script('WAIT_FOR_CAPS_ON\n', allow_unsafe=False)

    assert result['blocking'] is True
    assert result['error_count'] == 1
    assert result['unsafe_count'] == 1
    assert result['unsafe_commands'][0]['command'] == 'WAIT_FOR_CAPS_ON'
    assert result['unsafe_commands'][0]['severity'] == 'error'
    assert result['diagnostics'][0]['line'] == 1
    assert result['diagnostics'][0]['column'] == 1


def test_analyze_script_warns_for_unsafe_commands_when_enabled() -> None:
    result = analyze_script('WAIT_FOR_CAPS_ON\n', allow_unsafe=True)

    assert result['blocking'] is False
    assert result['warning_count'] == 1
    assert result['unsafe_commands'][0]['allowed'] is True
    assert result['unsafe_commands'][0]['severity'] == 'warning'


def test_analyze_script_reports_parse_errors_with_hint() -> None:
    result = analyze_script('IF TRUE\nSTRING hi\n', allow_unsafe=False)

    assert result['blocking'] is True
    assert result['parsed_commands'] == []
    assert result['diagnostics'][0]['code'] == 'parse_error'
    assert result['diagnostics'][0]['line'] == 1
    assert 'Close the current block' in result['diagnostics'][0]['hint']
