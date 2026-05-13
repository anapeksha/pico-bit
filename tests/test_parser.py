import pytest

from ducky import parse_script
from ducky.errors import DuckyParseError


def test_function_requires_empty_parens() -> None:
    with pytest.raises(DuckyParseError, match='FUNCTION must be declared as FUNCTION name\\(\\)'):
        parse_script('FUNCTION hello\nEND_FUNCTION\n')


def test_function_parameters_are_rejected() -> None:
    with pytest.raises(DuckyParseError, match='FUNCTION parameters are not supported'):
        parse_script('FUNCTION hello(name)\nEND_FUNCTION\n')


def test_rd_kbd_requires_platform_and_layout() -> None:
    with pytest.raises(DuckyParseError, match='RD_KBD requires a platform and layout'):
        parse_script('RD_KBD WIN\n')


def test_parse_script_accepts_valid_function_and_layout() -> None:
    statements = parse_script('FUNCTION hello()\nEND_FUNCTION\nRD_KBD WIN UK\n')

    assert statements[0]['kind'] == 'function'
    assert statements[0]['name'] == 'hello'
    assert statements[1]['kind'] == 'command'
    assert statements[1]['argument'] == 'WIN UK'


def test_invalid_expression_is_rejected_during_parse() -> None:
    with pytest.raises(DuckyParseError):
        parse_script('IF ($x == ) THEN\nEND_IF\n')


def test_parse_try_catch_end_try() -> None:
    stmts = parse_script('TRY\n  STRING hello\nCATCH\n  DELAY 100\nEND_TRY\n')

    assert len(stmts) == 1
    stmt = stmts[0]
    assert stmt['kind'] == 'try'
    assert len(stmt['try_body']) == 1
    assert stmt['try_body'][0]['kind'] == 'string'
    assert len(stmt['catch_body']) == 1
    assert stmt['catch_body'][0]['kind'] == 'command'


def test_parse_try_without_catch() -> None:
    stmts = parse_script('TRY\n  STRING hello\nEND_TRY\n')

    assert stmts[0]['kind'] == 'try'
    assert len(stmts[0]['try_body']) == 1
    assert stmts[0]['catch_body'] == []


def test_parse_try_missing_end_try_raises() -> None:
    with pytest.raises(DuckyParseError, match='missing END_TRY'):
        parse_script('TRY\n  STRING hello\n')


def test_parse_type_rate_accepts_expression() -> None:
    stmts = parse_script('TYPE_RATE 30\n')

    assert stmts[0]['kind'] == 'command'
    assert stmts[0]['command'] == 'TYPE_RATE'
    assert stmts[0]['argument'] == '30'


def test_parse_sleep_until_idle_accepts_expression() -> None:
    stmts = parse_script('SLEEP_UNTIL_IDLE 5000\n')

    assert stmts[0]['kind'] == 'command'
    assert stmts[0]['command'] == 'SLEEP_UNTIL_IDLE'


def test_parse_include_accepts_filename() -> None:
    stmts = parse_script('INCLUDE lib.dd\n')

    assert stmts[0]['kind'] == 'command'
    assert stmts[0]['command'] == 'INCLUDE'
    assert stmts[0]['argument'] == 'lib.dd'


def test_catch_outside_try_raises() -> None:
    with pytest.raises(DuckyParseError, match='unexpected CATCH'):
        parse_script('CATCH\n')
