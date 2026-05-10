import random

import machine

from helpers import sleep_ms
from keyboard import (
    DEFAULT_LAYOUT_CODE,
    MOD_ALIASES,
    MOD_NONE,
    hold_keys,
    release_keys,
    resolve_key_token,
    send_key,
    send_keys,
    type_string,
)

from .constants import (
    NO_DELAY_COMMANDS,
    RANDOM_CHAR_SETS,
    SAFE_INTERNAL_DEFAULTS,
)
from .errors import DuckyRuntimeError, RestartPayload, ReturnSignal, StopPayload
from .lexer import split_atoms, tokenize_expression
from .parser import parse_script

_YIELD_EVERY = 16


class DuckyInterpreter:
    def __init__(self, kbd, default_layout=DEFAULT_LAYOUT_CODE):
        self.kbd = kbd
        self.default_layout = default_layout
        self.default_delay_ms = 0
        self.default_char_delay_ms = 0
        self.variables = {}
        self.functions = {}
        self.extensions = {}
        self.button_handler = None
        self.last_action = None
        self._button = None
        self._led = None
        self._internal = {}
        self._ops_since_yield = 0
        for key, value in SAFE_INTERNAL_DEFAULTS.items():
            self._internal[key] = value

    async def run(self, statements):
        await self._execute_statements(statements)

    async def _checkpoint(self):
        self._ops_since_yield += 1
        if self._ops_since_yield >= _YIELD_EVERY:
            self._ops_since_yield = 0
            await sleep_ms(0)

    async def _execute_statements(self, statements):
        index = 0
        while index < len(statements):
            stmt = statements[index]
            kind = stmt['kind']

            if kind in ('function', 'extension', 'button'):
                await self._register_block(stmt)
                index += 1
                continue

            if kind == 'repeat':
                await self._repeat_last_action(stmt)
                index += 1
                continue

            await self._execute_statement(stmt)
            index += 1

    async def _register_block(self, stmt):
        kind = stmt['kind']
        if kind == 'function':
            self.functions[stmt['name']] = stmt['body']
        elif kind == 'extension':
            self.extensions[stmt['name']] = stmt['body']
            await self._execute_statements(stmt['body'])
        elif kind == 'button':
            self.button_handler = stmt['body']
            self._internal['_BUTTON_USER_DEFINED'] = True
        await self._checkpoint()

    async def _execute_statement(self, stmt):
        await self._checkpoint()
        kind = stmt['kind']

        if kind == 'assign':
            await self._execute_assign(stmt)
            self._remember_action(stmt)

        elif kind == 'if':
            await self._execute_if(stmt)

        elif kind == 'while':
            await self._execute_while(stmt)

        elif kind == 'call':
            await self._call_function(stmt['name'], stmt['line_no'])
            self._remember_action(None)

        elif kind == 'return':
            raise ReturnSignal(await self._eval_expr(stmt['expression'], stmt['line_no']))

        elif kind == 'string' or kind == 'string_block':
            await self._execute_string(stmt['text'], stmt['newline'])
            self._remember_action(stmt)

        elif kind == 'random_char':
            await self._execute_string(random.choice(RANDOM_CHAR_SETS[stmt['command']]), False)
            self._remember_action(stmt)

        elif kind == 'random_char_from':
            text = self._expand_text(stmt['argument'])
            if text:
                await self._execute_string(random.choice(text), False)
            self._remember_action(stmt)

        elif kind == 'hold':
            await self._execute_hold(stmt['combo'], stmt['line_no'])
            self._remember_action(stmt)

        elif kind == 'release':
            await self._execute_release(stmt['combo'], stmt['line_no'])
            self._remember_action(stmt)

        elif kind == 'combo':
            await self._tap_combo(stmt['combo'], stmt['line_no'])
            self._remember_action(stmt)

        elif kind == 'led':
            self._set_led(stmt['enabled'])
            self._remember_action(stmt)

        elif kind == 'command':
            await self._execute_command(stmt)
            await self._sleep_default_delay(stmt['command'])
            self._remember_action(stmt)

        else:
            raise DuckyRuntimeError(stmt['line_no'], f'unhandled statement type: {kind}')

    async def _repeat_last_action(self, stmt):
        if self.last_action is None:
            raise DuckyRuntimeError(stmt['line_no'], 'REPEAT used before any executable command')
        count = await self._eval_int(stmt['expression'], stmt['line_no'])
        if count < 0:
            count = 0
        for _ in range(count):
            await self.last_action()

    def _remember_action(self, stmt):
        if stmt is None:
            self.last_action = None
            return

        async def runner(statement=stmt):
            await self._execute_statement(statement)

        self.last_action = runner

    async def _execute_if(self, stmt):
        for branch in stmt['branches']:
            if await self._eval_bool(branch['condition'], branch['line_no']):
                await self._execute_statements(branch['body'])
                return
        if stmt['else_body']:
            await self._execute_statements(stmt['else_body'])

    async def _execute_while(self, stmt):
        while await self._eval_bool(stmt['condition'], stmt['line_no']):
            await self._execute_statements(stmt['body'])

    async def _execute_assign(self, stmt):
        value = await self._eval_expr(stmt['expression'], stmt['line_no'])
        current = self._get_symbol(stmt['name'])
        operator = stmt['operator']

        if operator == '=':
            result = value
        elif operator == '+=':
            result = current + value
        elif operator == '-=':
            result = current - value
        elif operator == '*=':
            result = current * value
        elif operator == '/=':
            result = current / value
        elif operator == '%=':
            result = current % value
        elif operator == '&=':
            result = int(current) & int(value)
        elif operator == '|=':
            result = int(current) | int(value)
        elif operator == '^=':
            result = current**value
        elif operator == '<<=':
            result = int(current) << int(value)
        elif operator == '>>=':
            result = int(current) >> int(value)
        else:
            raise DuckyRuntimeError(stmt['line_no'], f'unsupported assignment operator: {operator}')

        self._set_symbol(stmt['name'], result)

    async def _execute_command(self, stmt):
        command = stmt['command']
        argument = stmt['argument']
        line_no = stmt['line_no']

        if command == 'DELAY':
            await sleep_ms(await self._eval_int(argument, line_no))
            return

        if command in ('DEFAULTDELAY', 'DEFAULT_DELAY'):
            self.default_delay_ms = await self._eval_int(argument, line_no)
            return

        if command in ('DEFAULTCHARDELAY', 'DEFAULT_CHAR_DELAY'):
            self.default_char_delay_ms = await self._eval_int(argument, line_no)
            return

        if command == 'DEFAULTCHARJITTER':
            self._internal['_JITTER_ENABLED'] = True
            self._internal['_JITTER_MAX'] = max(0, await self._eval_int(argument, line_no))
            return

        if command == 'VERSION':
            return

        if command == 'RD_KBD':
            # Target OS/layout are portal-managed on this firmware, so RD_KBD
            # is accepted for compatibility but does not override selection.
            return

        if command == 'WAIT_FOR_BUTTON_PRESS':
            await self._wait_for_button_press()
            return

        if command == 'ENABLE_BUTTON':
            self._internal['_BUTTON_ENABLED'] = True
            return

        if command == 'DISABLE_BUTTON':
            self._internal['_BUTTON_ENABLED'] = False
            return

        if command == 'RESET':
            await self.kbd.release_all()
            return

        if command == 'STOP_PAYLOAD':
            raise StopPayload()

        if command == 'RESTART_PAYLOAD':
            raise RestartPayload()

        if command == 'INJECT_MOD':
            await self._tap_combo(argument, line_no)
            return

        if command == 'INJECT_VAR':
            value = await self._eval_expr(argument, line_no)
            if isinstance(value, int):
                await send_key(self.kbd, MOD_NONE, value)
            else:
                await self._execute_string(str(value), False)
            return

        if command in (
            'ATTACKMODE',
            'HIDE_PAYLOAD',
            'RESTORE_PAYLOAD',
            'SAVE_ATTACKMODE',
            'RESTORE_ATTACKMODE',
            'EXFIL',
        ):
            raise DuckyRuntimeError(
                line_no, f'{command} is not implemented on this MicroPython target'
            )

        raise DuckyRuntimeError(line_no, f'unsupported command: {command}')

    async def _execute_string(self, text, newline):
        expanded = self._expand_text(text)
        if newline:
            for line in expanded.split('\n'):
                await self._type_text(line)
                await send_key(self.kbd, MOD_NONE, 0x28)
        else:
            parts = expanded.split('\n')
            for index, part in enumerate(parts):
                await self._type_text(part)
                if index != len(parts) - 1:
                    await send_key(self.kbd, MOD_NONE, 0x28)
        await self._sleep_default_delay('STRINGLN' if newline else 'STRING')

    async def _type_text(self, text):
        await type_string(
            self.kbd,
            text,
            self._char_delay_ms(),
            layout_code=self.default_layout,
        )

    def _char_delay_ms(self):
        delay = max(0, self.default_char_delay_ms)
        if self._internal.get('_JITTER_ENABLED'):
            jitter_max = int(self._internal.get('_JITTER_MAX', 0))
            if jitter_max > 0:
                delay += random.randint(0, jitter_max)
        return delay

    async def _sleep_default_delay(self, command):
        if command not in NO_DELAY_COMMANDS and self.default_delay_ms > 0:
            await sleep_ms(self.default_delay_ms)

    async def _execute_hold(self, combo, line_no):
        modifier, keycodes = self._parse_combo(combo, line_no)
        await hold_keys(self.kbd, modifier, keycodes)
        await self._sleep_default_delay('HOLD')

    async def _execute_release(self, combo, line_no):
        if combo:
            modifier, keycodes = self._parse_combo(combo, line_no)
        else:
            modifier = 0
            keycodes = []
        await release_keys(self.kbd, modifier, keycodes)
        await self._sleep_default_delay('RELEASE')

    async def _tap_combo(self, combo, line_no):
        modifier, keycodes = self._parse_combo(combo, line_no)
        await send_keys(self.kbd, modifier, keycodes)
        await self._sleep_default_delay(combo.split(None, 1)[0].upper() if combo else '')

    def _parse_combo(self, text, line_no):
        modifier = 0
        keycodes = []

        for token in split_atoms(text, line_no):
            upper = token.upper()
            if upper in MOD_ALIASES:
                modifier |= MOD_ALIASES[upper]
                continue
            key_mod, keycode = resolve_key_token(token)
            if keycode == 0 and key_mod == 0:
                raise DuckyRuntimeError(line_no, f'unknown key token: {token}')
            modifier |= key_mod
            if keycode:
                keycodes.append(keycode)

        return modifier, keycodes

    def _expand_text(self, text):
        out = []
        index = 0
        while index < len(text):
            if text[index] == '$':
                if index + 1 < len(text) and text[index + 1] == '$':
                    out.append('$')
                    index += 2
                    continue

                if index + 1 >= len(text) or not (
                    text[index + 1].isalpha() or text[index + 1] == '_'
                ):
                    out.append('$')
                    index += 1
                    continue

                end = index + 1
                while end < len(text) and (text[end].isalnum() or text[end] == '_'):
                    end += 1

                name = text[index + 1 : end]
                if self._has_symbol(name):
                    out.append(str(self._get_symbol(name)))
                else:
                    out.append(text[index:end])
                index = end
            else:
                out.append(text[index])
                index += 1
        return ''.join(out)

    async def _translate_expr(self, expr):
        translated = []
        tokens = tokenize_expression(expr, 0)
        index = 0

        while index < len(tokens):
            token = tokens[index]

            if token.kind == 'VARIABLE':
                translated.append(repr(self._get_symbol(token.value[1:])))
                index += 1
                continue

            if token.kind == 'IDENTIFIER':
                upper = token.value.upper()
                if upper == 'TRUE':
                    translated.append('True')
                elif upper == 'FALSE':
                    translated.append('False')
                elif upper == 'AND':
                    translated.append('and')
                elif upper == 'OR':
                    translated.append('or')
                elif upper == 'NOT':
                    translated.append('not')
                elif (
                    index + 2 < len(tokens)
                    and tokens[index + 1].kind == 'LPAREN'
                    and tokens[index + 2].kind == 'RPAREN'
                ):
                    translated.append(repr(await self._call_function(token.value, token.line_no)))
                    index += 2
                else:
                    translated.append(token.value)
                index += 1
                continue

            if token.kind == 'OPERATOR':
                if token.value == '&&':
                    translated.append('and')
                elif token.value == '||':
                    translated.append('or')
                elif token.value == '!':
                    translated.append('not')
                elif token.value == '^':
                    translated.append('**')
                else:
                    translated.append(token.value)
                index += 1
                continue

            translated.append(token.value)
            index += 1

        return ' '.join(translated)

    async def _eval_bool(self, expr, line_no):
        return bool(await self._eval_expr(expr, line_no))

    async def _eval_int(self, expr, line_no):
        value = await self._eval_expr(expr, line_no)
        try:
            return int(value)
        except Exception as exc:
            raise DuckyRuntimeError(line_no, f'integer expected, got {value!r}') from exc

    async def _eval_expr(self, expr, line_no):
        translated = await self._translate_expr(expr.strip())
        env: dict[str, object] = {}

        for name in self.functions:
            env[name] = self._make_function_placeholder(name)

        try:
            return eval(translated, {'__builtins__': {}}, env)
        except ReturnSignal:
            raise
        except DuckyRuntimeError:
            raise
        except Exception as exc:
            raise DuckyRuntimeError(line_no, f'invalid expression: {expr}') from exc

    def _make_function_placeholder(self, name):
        def caller():
            return name

        return caller

    async def _call_function(self, name, line_no):
        if name not in self.functions:
            raise DuckyRuntimeError(line_no, f'unknown function: {name}')
        try:
            await self._execute_statements(self.functions[name])
        except ReturnSignal as signal:
            return signal.value
        return 0

    def _get_symbol(self, name):
        if name.startswith('_'):
            return self._get_internal(name)
        if name in self.variables:
            return self.variables[name]
        return 0

    def _has_symbol(self, name):
        return name.startswith('_') or name in self.variables

    def _set_symbol(self, name, value):
        if name.startswith('_'):
            self._set_internal(name, value)
        else:
            self.variables[name] = value

    def _get_internal(self, name):
        if name == '_RANDOM_INT':
            min_value = int(self._internal.get('_RANDOM_MIN', 0))
            max_value = int(self._internal.get('_RANDOM_MAX', 65535))
            if min_value > max_value:
                min_value, max_value = max_value, min_value
            return random.randint(min_value, max_value)

        return self._internal.get(name, 0)

    def _set_internal(self, name, value):
        self._internal[name] = value

    async def _wait_for_button_press(self):
        if self._button is None:
            self._button = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
        while self._button.value():
            await sleep_ms(50)
        while not self._button.value():
            await sleep_ms(50)

    def _set_led(self, enabled):
        if self._led is None:
            try:
                self._led = machine.Pin('LED', machine.Pin.OUT)
            except Exception:
                return
        self._led.value(1 if enabled else 0)


async def run_script(
    kbd,
    script: str,
    default_layout: str = DEFAULT_LAYOUT_CODE,
) -> None:
    statements = parse_script(script)
    while True:
        try:
            interpreter = DuckyInterpreter(kbd, default_layout=default_layout)
            await interpreter.run(statements)
            return
        except RestartPayload:
            continue
        except StopPayload:
            return
