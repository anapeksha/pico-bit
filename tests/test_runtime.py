import asyncio

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
