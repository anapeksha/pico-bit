"""
DuckyScript lexing utilities.
"""

from .errors import DuckyParseError

_COMMAND_SEPARATORS = {'-', '(', ')', ','}
_EXPR_MULTI_OPERATORS = (
    '<<=',
    '>>=',
    '+=',
    '-=',
    '*=',
    '/=',
    '%=',
    '&=',
    '|=',
    '^=',
    '&&',
    '||',
    '<<',
    '>>',
    '<=',
    '>=',
    '==',
    '!=',
)
_EXPR_SINGLE_OPERATORS = set('+-*/%&|^!=<>=')
_EXPR_PUNCTUATION = {
    '(': 'LPAREN',
    ')': 'RPAREN',
    ',': 'COMMA',
}


class Token:
    __slots__ = ('kind', 'value', 'line_no', 'column')

    def __init__(self, kind, value, line_no, column):
        self.kind = kind
        self.value = value
        self.line_no = line_no
        self.column = column


class LexedLine:
    __slots__ = (
        'line_no',
        'raw',
        'stripped',
        'upper',
        'keyword',
        'argument',
        'tokens',
        'atoms',
        'is_blank',
        'is_comment',
    )

    def __init__(
        self,
        line_no,
        raw,
        stripped,
        upper,
        keyword,
        argument,
        tokens,
        atoms,
        is_blank,
        is_comment,
    ):
        self.line_no = line_no
        self.raw = raw
        self.stripped = stripped
        self.upper = upper
        self.keyword = keyword
        self.argument = argument
        self.tokens = tokens
        self.atoms = atoms
        self.is_blank = is_blank
        self.is_comment = is_comment


def _expression_error(line_no, message, token=None):
    if token is None:
        raise DuckyParseError(line_no, message)
    raise DuckyParseError(line_no, f'{message} at column {token.column}')


def _is_comment_text(text):
    upper = text.upper()
    return upper == 'REM' or upper.startswith('REM ') or upper.startswith('//')


def _split_keyword_argument(text):
    if not text:
        return '', ''
    parts = text.split(None, 1)
    keyword = parts[0].upper()
    argument = parts[1] if len(parts) > 1 else ''
    return keyword, argument


def tokenize_command_text(text, line_no):
    tokens = []
    index = 0

    while index < len(text):
        ch = text[index]
        column = index + 1

        if ch in (' ', '\t'):
            start = index
            while index < len(text) and text[index] in (' ', '\t'):
                index += 1
            tokens.append(Token('SPACE', text[start:index], line_no, column))
            continue

        if ch in _COMMAND_SEPARATORS:
            tokens.append(Token('SEPARATOR', ch, line_no, column))
            index += 1
            continue

        start = index
        while (
            index < len(text)
            and text[index] not in _COMMAND_SEPARATORS
            and text[index] not in (' ', '\t')
        ):
            index += 1
        tokens.append(Token('ATOM', text[start:index], line_no, column))

    return tokens


def split_atoms(text, line_no=0):
    tokens = tokenize_command_text(text, line_no)
    return [token.value for token in tokens if token.kind == 'ATOM']


def lex_line(line_no, raw):
    stripped = raw.strip()
    upper = stripped.upper()
    is_blank = not stripped
    is_comment = _is_comment_text(stripped) if stripped else False
    keyword, argument = _split_keyword_argument(stripped)
    tokens = tuple(tokenize_command_text(raw, line_no))
    atoms = tuple(token.value for token in tokens if token.kind == 'ATOM')
    return LexedLine(
        line_no,
        raw,
        stripped,
        upper,
        keyword,
        argument,
        tokens,
        atoms,
        is_blank,
        is_comment,
    )


def lex_script(script):
    lines = script.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    processed = []
    defines = {}
    in_rem_block = False

    for line_no, raw in enumerate(lines, 1):
        stripped = raw.strip()
        upper = stripped.upper()

        if in_rem_block:
            if upper in ('END_REM', 'ENDREM'):
                in_rem_block = False
            continue

        if upper == 'REM_BLOCK':
            in_rem_block = True
            continue

        if upper.startswith('DEFINE '):
            parts = stripped.split(None, 2)
            if len(parts) != 3:
                raise DuckyParseError(line_no, 'DEFINE requires a name and value')
            defines[parts[1]] = parts[2]
            continue

        line = raw.rstrip()
        for key, value in defines.items():
            if key in line:
                line = line.replace(key, value)
        processed.append(lex_line(line_no, line))

    return processed


def tokenize_expression(expr, line_no):
    tokens = []
    index = 0

    while index < len(expr):
        ch = expr[index]
        column = index + 1

        if ch in (' ', '\t'):
            index += 1
            continue

        matched = None
        for operator in _EXPR_MULTI_OPERATORS:
            if expr.startswith(operator, index):
                matched = operator
                break
        if matched is not None:
            tokens.append(Token('OPERATOR', matched, line_no, column))
            index += len(matched)
            continue

        if ch in _EXPR_SINGLE_OPERATORS:
            tokens.append(Token('OPERATOR', ch, line_no, column))
            index += 1
            continue

        if ch in _EXPR_PUNCTUATION:
            tokens.append(Token(_EXPR_PUNCTUATION[ch], ch, line_no, column))
            index += 1
            continue

        if ch == '$':
            start = index
            index += 1
            if index >= len(expr) or not (expr[index].isalpha() or expr[index] == '_'):
                raise DuckyParseError(line_no, f'invalid variable reference at column {column}')
            while index < len(expr) and (
                expr[index].isalpha() or expr[index].isdigit() or expr[index] == '_'
            ):
                index += 1
            tokens.append(Token('VARIABLE', expr[start:index], line_no, column))
            continue

        if ch in ('"', "'"):
            quote = ch
            start = index
            index += 1
            escaped = False
            while index < len(expr):
                current = expr[index]
                if escaped:
                    escaped = False
                elif current == '\\':
                    escaped = True
                elif current == quote:
                    index += 1
                    break
                index += 1
            else:
                raise DuckyParseError(line_no, f'unterminated string literal at column {column}')
            tokens.append(Token('STRING', expr[start:index], line_no, column))
            continue

        if ch.isdigit():
            start = index
            index += 1
            if ch == '0' and index < len(expr) and expr[index] in ('x', 'X'):
                index += 1
                while index < len(expr) and expr[index] in '0123456789abcdefABCDEF':
                    index += 1
            else:
                while index < len(expr) and (expr[index].isdigit() or expr[index] == '.'):
                    index += 1
            tokens.append(Token('NUMBER', expr[start:index], line_no, column))
            continue

        if ch.isalpha() or ch == '_':
            start = index
            index += 1
            while index < len(expr) and (
                expr[index].isalpha() or expr[index].isdigit() or expr[index] == '_'
            ):
                index += 1
            tokens.append(Token('IDENTIFIER', expr[start:index], line_no, column))
            continue

        raise DuckyParseError(
            line_no, f'unexpected character in expression: {ch!r} at column {column}'
        )

    return tokens


def _is_identifier_value(token, value):
    return token.kind == 'IDENTIFIER' and token.value.upper() == value


def _is_prefix_operator(token):
    return (token.kind == 'OPERATOR' and token.value in ('!', '+', '-')) or _is_identifier_value(
        token, 'NOT'
    )


def _is_infix_operator(token):
    return (
        token.kind == 'OPERATOR'
        and token.value
        in (
            '&&',
            '||',
            '<<',
            '>>',
            '<=',
            '>=',
            '==',
            '!=',
            '<',
            '>',
            '+',
            '-',
            '*',
            '/',
            '%',
            '&',
            '|',
            '^',
        )
        or _is_identifier_value(token, 'AND')
        or _is_identifier_value(token, 'OR')
    )


def _parse_expression_operand(tokens, index, line_no):
    while index < len(tokens) and _is_prefix_operator(tokens[index]):
        index += 1

    if index >= len(tokens):
        _expression_error(line_no, 'expression ended where a value was expected')
        raise AssertionError('unreachable')

    token = tokens[index]

    if token.kind == 'LPAREN':
        index = _parse_expression_sequence(tokens, index + 1, line_no)
        if index >= len(tokens) or tokens[index].kind != 'RPAREN':
            _expression_error(line_no, 'missing closing parenthesis', token)
            raise AssertionError('unreachable')
        return index + 1

    if token.kind in ('VARIABLE', 'NUMBER', 'STRING'):
        return index + 1

    if token.kind == 'IDENTIFIER':
        if token.value.upper() in ('AND', 'OR', 'NOT'):
            _expression_error(line_no, 'operator used where a value was expected', token)
            raise AssertionError('unreachable')

        index += 1
        if index < len(tokens) and tokens[index].kind == 'LPAREN':
            call_start = tokens[index]
            index += 1
            if index >= len(tokens) or tokens[index].kind != 'RPAREN':
                _expression_error(
                    line_no, 'only zero-argument function calls are supported', call_start
                )
                raise AssertionError('unreachable')
            index += 1
        return index

    _expression_error(line_no, 'unexpected token in expression', token)
    raise AssertionError('unreachable')


def _parse_expression_sequence(tokens, index, line_no):
    index = _parse_expression_operand(tokens, index, line_no)

    while index < len(tokens):
        token = tokens[index]
        if token.kind == 'RPAREN':
            break
        if not _is_infix_operator(token):
            _expression_error(line_no, 'operator expected', token)
            raise AssertionError('unreachable')
        index = _parse_expression_operand(tokens, index + 1, line_no)

    return index


def validate_expression_tokens(tokens, line_no):
    if not tokens:
        raise DuckyParseError(line_no, 'expression is empty')
    index = _parse_expression_sequence(tokens, 0, line_no)
    if index != len(tokens):
        _expression_error(line_no, 'unexpected trailing token', tokens[index])
