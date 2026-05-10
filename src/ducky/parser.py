"""
DuckyScript parsing.
"""

from keyboard import MOD_ALIASES, resolve_key_token

from .constants import BLOCK_TERMINATORS, LED_ON_COMMANDS, RANDOM_CHAR_SETS, SIMPLE_COMMANDS
from .errors import DuckyParseError
from .lexer import lex_script, split_atoms, tokenize_expression, validate_expression_tokens

_EXPRESSION_COMMANDS = {
    'DEFAULTDELAY',
    'DEFAULT_DELAY',
    'DEFAULTCHARDELAY',
    'DEFAULT_CHAR_DELAY',
    'DEFAULTCHARJITTER',
    'DELAY',
    'INJECT_VAR',
}


def _dedent_block(lines):
    if not lines:
        return ''

    indent = None
    for line in lines:
        if line.strip():
            count = 0
            while count < len(line) and line[count] == ' ':
                count += 1
            if indent is None or count < indent:
                indent = count

    if indent is None or indent == 0:
        return '\n'.join(lines)

    stripped = []
    for line in lines:
        if line.startswith(' ' * indent):
            stripped.append(line[indent:])
        else:
            stripped.append(line.lstrip(' '))
    return '\n'.join(stripped)


def _make_stmt(kind, line_no, **fields):
    stmt = {
        'kind': kind,
        'line_no': line_no,
    }
    for key, value in fields.items():
        stmt[key] = value
    return stmt


class _Parser:
    def __init__(self, lines):
        self.lines = lines

    def parse(self):
        statements, index, terminator = self._parse_block(0, ())
        if terminator is not None:
            line_no = self.lines[index].line_no
            raise DuckyParseError(line_no, f'unexpected {terminator}')
        return statements

    def _parse_block(self, index, end_tokens):
        statements = []

        while index < len(self.lines):
            line = self.lines[index]

            if line.is_blank or line.is_comment:
                index += 1
                continue

            matched = self._match_terminator(line.upper, end_tokens)
            if matched is not None:
                return statements, index, matched

            if line.upper in BLOCK_TERMINATORS:
                return statements, index, line.upper

            if line.upper.startswith('IF '):
                stmt, index = self._parse_if(index)
                statements.append(stmt)
                continue

            if line.upper.startswith('WHILE '):
                stmt, index = self._parse_while(index)
                statements.append(stmt)
                continue

            if line.upper.startswith('FUNCTION '):
                stmt, index = self._parse_named_block(index, 'FUNCTION', 'END_FUNCTION', 'function')
                statements.append(stmt)
                continue

            if line.upper.startswith('EXTENSION '):
                stmt, index = self._parse_named_block(
                    index, 'EXTENSION', 'END_EXTENSION', 'extension'
                )
                statements.append(stmt)
                continue

            if line.upper == 'BUTTON_DEF':
                stmt, index = self._parse_button(index)
                statements.append(stmt)
                continue

            if line.upper == 'STRING':
                stmt, index = self._parse_multiline(index, 'END_STRING', 'string_block', False)
                statements.append(stmt)
                continue

            if line.upper == 'STRINGLN':
                stmt, index = self._parse_multiline(index, 'END_STRINGLN', 'string_block', True)
                statements.append(stmt)
                continue

            statements.append(self._parse_simple(line))
            index += 1

        return statements, index, None

    def _match_terminator(self, upper, end_tokens):
        for token in end_tokens:
            if token in ('ELSE IF', 'ELSEIF'):
                if (
                    upper.startswith('ELSE IF ')
                    or upper == 'ELSE IF'
                    or upper.startswith('ELSEIF ')
                    or upper == 'ELSEIF'
                ):
                    return token
            elif upper == token:
                return token
        return None

    def _parse_if(self, index):
        line = self.lines[index]
        condition = self._strip_condition_suffix(line.argument, 'THEN')
        self._validate_expression(condition, line.line_no, 'IF requires a condition')
        index += 1

        branches = []
        body, index, terminator = self._parse_block(index, ('ELSE IF', 'ELSEIF', 'ELSE', 'END_IF'))
        branches.append(
            {
                'line_no': line.line_no,
                'condition': condition,
                'body': body,
            }
        )

        while terminator in ('ELSE IF', 'ELSEIF'):
            branch_line = self.lines[index]
            branch_condition = self._parse_else_if_condition(branch_line.stripped)
            self._validate_expression(
                branch_condition, branch_line.line_no, 'ELSE IF requires a condition'
            )
            index += 1
            body, index, terminator = self._parse_block(
                index, ('ELSE IF', 'ELSEIF', 'ELSE', 'END_IF')
            )
            branches.append(
                {
                    'line_no': branch_line.line_no,
                    'condition': branch_condition,
                    'body': body,
                }
            )

        else_body = []
        if terminator == 'ELSE':
            index += 1
            else_body, index, terminator = self._parse_block(index, ('END_IF',))

        if terminator != 'END_IF':
            raise DuckyParseError(line.line_no, 'missing END_IF')

        return _make_stmt('if', line.line_no, branches=branches, else_body=else_body), index + 1

    def _parse_while(self, index):
        line = self.lines[index]
        condition = self._strip_wrapping_parens(line.argument)
        self._validate_expression(condition, line.line_no, 'WHILE requires a condition')
        index += 1
        body, index, terminator = self._parse_block(index, ('END_WHILE',))
        if terminator != 'END_WHILE':
            raise DuckyParseError(line.line_no, 'missing END_WHILE')
        return _make_stmt('while', line.line_no, condition=condition, body=body), index + 1

    def _parse_named_block(self, index, prefix, end_token, kind):
        line = self.lines[index]
        name = line.argument.strip()
        if kind == 'function':
            name = self._parse_function_name(line)
        elif not name:
            raise DuckyParseError(line.line_no, f'{prefix} requires a name')
        index += 1
        body, index, terminator = self._parse_block(index, (end_token,))
        if terminator != end_token:
            raise DuckyParseError(line.line_no, f'missing {end_token}')
        return _make_stmt(kind, line.line_no, name=name, body=body), index + 1

    def _parse_button(self, index):
        line = self.lines[index]
        index += 1
        body, index, terminator = self._parse_block(index, ('END_BUTTON',))
        if terminator != 'END_BUTTON':
            raise DuckyParseError(line.line_no, 'missing END_BUTTON')
        return _make_stmt('button', line.line_no, body=body), index + 1

    def _parse_multiline(self, index, end_token, kind, newline):
        line = self.lines[index]
        index += 1
        body_lines = []

        while index < len(self.lines):
            current = self.lines[index]
            if current.upper == end_token:
                text = _dedent_block(body_lines)
                return _make_stmt(kind, line.line_no, text=text, newline=newline), index + 1
            body_lines.append(current.raw)
            index += 1

        raise DuckyParseError(line.line_no, f'missing {end_token}')

    def _parse_simple(self, line):
        if line.keyword == 'VAR':
            return self._parse_assignment(line.line_no, line.argument, True)

        if line.stripped.startswith('$'):
            return self._parse_assignment(line.line_no, line.stripped, False)

        command = line.keyword
        arg = line.argument

        if command in RANDOM_CHAR_SETS:
            return _make_stmt('random_char', line.line_no, command=command)

        if command == 'RANDOM_CHAR_FROM':
            return _make_stmt('random_char_from', line.line_no, argument=arg)

        if command == 'STRING':
            return _make_stmt('string', line.line_no, text=arg, newline=False)

        if command == 'STRINGLN':
            return _make_stmt('string', line.line_no, text=arg, newline=True)

        if command == 'REPEAT':
            self._validate_expression(
                arg or '1', line.line_no, 'REPEAT requires a count expression'
            )
            return _make_stmt('repeat', line.line_no, expression=arg or '1')

        if command == 'RETURN':
            self._validate_expression(arg or '0', line.line_no, 'RETURN requires an expression')
            return _make_stmt('return', line.line_no, expression=arg or '0')

        if command == 'HOLD':
            return _make_stmt('hold', line.line_no, combo=arg)

        if command == 'RELEASE':
            return _make_stmt('release', line.line_no, combo=arg)

        if command in LED_ON_COMMANDS:
            return _make_stmt('led', line.line_no, enabled=True, color=command)

        if command == 'LED_OFF':
            return _make_stmt('led', line.line_no, enabled=False, color=command)

        if command in SIMPLE_COMMANDS:
            if command in _EXPRESSION_COMMANDS:
                self._validate_expression(arg, line.line_no, f'{command} requires an expression')
            if command == 'RD_KBD':
                self._validate_rd_kbd(arg, line.line_no)
            return _make_stmt('command', line.line_no, command=command, argument=arg)

        if self._is_function_call(line.stripped):
            return _make_stmt('call', line.line_no, name=line.stripped.split('(', 1)[0].strip())

        if self._is_combo(line.stripped):
            return _make_stmt('combo', line.line_no, combo=line.stripped)

        raise DuckyParseError(line.line_no, f'unknown command: {line.keyword or line.stripped}')

    def _parse_assignment(self, line_no, statement, declared):
        operators = ('<<=', '>>=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '=')
        for operator in operators:
            if operator in statement:
                name, expression = statement.split(operator, 1)
                name = name.strip()
                if not name.startswith('$'):
                    raise DuckyParseError(line_no, 'assignment target must start with $')
                name = name[1:]
                if not name:
                    raise DuckyParseError(line_no, 'assignment target is empty')
                expression = expression.strip()
                self._validate_expression(expression, line_no, 'assignment requires an expression')
                return _make_stmt(
                    'assign',
                    line_no,
                    name=name,
                    operator=operator,
                    expression=expression,
                    declared=declared,
                )
        raise DuckyParseError(line_no, 'invalid assignment syntax')

    def _parse_else_if_condition(self, line):
        upper = line.upper()
        prefix = len('ELSE IF') if upper.startswith('ELSE IF') else len('ELSEIF')
        return self._strip_condition_suffix(line[prefix:].strip(), 'THEN')

    def _parse_function_name(self, line):
        signature = line.argument.strip()
        if not signature:
            raise DuckyParseError(line.line_no, 'FUNCTION requires a name')
        if not signature.endswith(')') or '(' not in signature:
            raise DuckyParseError(line.line_no, 'FUNCTION must be declared as FUNCTION name()')

        name, params = signature[:-1].split('(', 1)
        name = name.strip()
        params = params.strip()

        if not name:
            raise DuckyParseError(line.line_no, 'FUNCTION requires a name')
        if params:
            raise DuckyParseError(line.line_no, 'FUNCTION parameters are not supported')
        return name

    def _validate_rd_kbd(self, argument, line_no):
        parts = split_atoms(argument, line_no)
        if len(parts) != 2:
            raise DuckyParseError(line_no, 'RD_KBD requires a platform and layout')

    def _strip_condition_suffix(self, text, suffix):
        upper = text.upper()
        if upper.endswith(suffix):
            text = text[: len(text) - len(suffix)].strip()
        return self._strip_wrapping_parens(text)

    def _strip_wrapping_parens(self, text):
        while text.startswith('(') and text.endswith(')'):
            text = text[1:-1].strip()
        return text

    def _validate_expression(self, expr, line_no, empty_message):
        if not expr.strip():
            raise DuckyParseError(line_no, empty_message)
        validate_expression_tokens(tokenize_expression(expr, line_no), line_no)

    def _is_function_call(self, text):
        return text.endswith('()') and ' ' not in text and '(' in text

    def _is_combo(self, text):
        for token in split_atoms(text):
            upper = token.upper()
            if upper in MOD_ALIASES:
                continue
            _, keycode = resolve_key_token(token)
            if keycode == 0:
                return False
        return True


def parse_script(script):
    return _Parser(lex_script(script)).parse()


def validate_script(script):
    return parse_script(script)
