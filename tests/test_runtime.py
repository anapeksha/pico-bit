import asyncio

import pytest

from ducky.errors import DuckyRuntimeError
from ducky.runtime import DuckyInterpreter


class FakeKeyboard:
    def release_all(self) -> None:
        pass


def test_expand_text_keeps_literal_dollar_for_unknown_names() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())

    assert interpreter._expand_text('echo $HOME') == 'echo $HOME'
    assert interpreter._expand_text('price is $1') == 'price is $1'
    assert interpreter._expand_text('literal $env:TEMP') == 'literal $env:TEMP'


def test_expand_text_only_expands_known_symbols() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())
    interpreter.variables['name'] = 'pico'
    interpreter._internal['_BUTTON_TIMEOUT'] = 250

    assert interpreter._expand_text('hello $name') == 'hello pico'
    assert interpreter._expand_text('timeout=$_BUTTON_TIMEOUT') == 'timeout=250'


def test_expand_text_supports_escaped_dollar_sign() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())

    assert interpreter._expand_text('cost $$5') == 'cost $5'


def test_eval_expr_supports_async_function_calls() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())
    interpreter.functions['answer'] = [
        {
            'kind': 'return',
            'line_no': 1,
            'expression': '41',
        }
    ]

    value = asyncio.run(interpreter._eval_expr('answer() + 1', 1))

    assert value == 42


def test_type_rate_sets_char_delay() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())
    stmt = {'kind': 'command', 'command': 'TYPE_RATE', 'argument': '10', 'line_no': 1}

    asyncio.run(interpreter._execute_command(stmt))

    assert interpreter.default_char_delay_ms == 100  # 1000 // 10


def test_type_rate_zero_sets_zero_delay() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())
    interpreter.default_char_delay_ms = 50
    stmt = {'kind': 'command', 'command': 'TYPE_RATE', 'argument': '0', 'line_no': 1}

    asyncio.run(interpreter._execute_command(stmt))

    assert interpreter.default_char_delay_ms == 0


def test_sleep_until_idle_accepts_zero_without_sleeping() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())
    stmt = {'kind': 'command', 'command': 'SLEEP_UNTIL_IDLE', 'argument': '0', 'line_no': 1}

    # Should not raise and complete promptly.
    asyncio.run(interpreter._execute_command(stmt))


def test_attackmode_exfil_hide_payload_are_no_ops() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())
    for command in (
        'ATTACKMODE',
        'EXFIL',
        'HIDE_PAYLOAD',
        'RESTORE_ATTACKMODE',
        'RESTORE_PAYLOAD',
        'SAVE_ATTACKMODE',
    ):
        stmt = {'kind': 'command', 'command': command, 'argument': '', 'line_no': 1}
        asyncio.run(interpreter._execute_command(stmt))  # must not raise


def test_try_catch_executes_catch_on_runtime_error() -> None:
    """Errors in the try body should invoke the catch handler."""
    interpreter = DuckyInterpreter(FakeKeyboard())
    log: list[str] = []

    async def run() -> None:
        stmt = {
            'kind': 'try',
            'line_no': 1,
            'try_body': [
                {
                    'kind': 'command',
                    'command': 'nonexistent_cmd_xyz',
                    'argument': '',
                    'line_no': 2,
                }
            ],
            'catch_body': [],
        }
        try:
            await interpreter._execute_try(stmt)
        except DuckyRuntimeError:
            log.append('uncaught')

    asyncio.run(run())
    # Error inside try body should be caught silently (catch_body is empty → no re-raise)
    assert 'uncaught' not in log


def test_try_without_catch_propagates_non_runtime_errors() -> None:
    """StopPayload and RestartPayload must escape TRY blocks unchanged."""
    from ducky.errors import StopPayload

    interpreter = DuckyInterpreter(FakeKeyboard())

    async def run() -> None:
        stmt = {
            'kind': 'try',
            'line_no': 1,
            'try_body': [
                {'kind': 'command', 'command': 'STOP_PAYLOAD', 'argument': '', 'line_no': 2}
            ],
            'catch_body': [],
        }
        await interpreter._execute_try(stmt)

    with pytest.raises(StopPayload):
        asyncio.run(run())


def test_include_raises_on_missing_file() -> None:
    interpreter = DuckyInterpreter(FakeKeyboard())

    with pytest.raises(DuckyRuntimeError, match='INCLUDE: file not found'):
        asyncio.run(interpreter._execute_include('/nonexistent/path/script.dd', 1))


def test_include_executes_script_from_file(tmp_path) -> None:
    script_file = tmp_path / 'lib.dd'
    script_file.write_text('VAR $counter = 42\n', encoding='utf-8')

    interpreter = DuckyInterpreter(FakeKeyboard())

    asyncio.run(interpreter._execute_include(str(script_file), 1))

    assert interpreter.variables.get('counter') == 42
