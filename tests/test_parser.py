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
