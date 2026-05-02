import re

from .constants import UNSAFE_COMMANDS, UNSAFE_INTERNALS
from .errors import DuckyScriptError
from .lexer import lex_script
from .parser import parse_script

_COLUMN_RE = re.compile(r' at column (\d+)$')
_UNSAFE_INTERNAL_PREFIXES = ('_CAPSLOCK_', '_NUMLOCK_', '_SCROLLLOCK_', '_EXFIL_')
_MULTILINE_ENDINGS = {
    'STRING': 'END_STRING',
    'STRINGLN': 'END_STRINGLN',
}


def _line_count(script: str) -> int:
    return max(1, script.count('\n') + 1)


def _strip_column_suffix(message: str) -> tuple[str, int | None]:
    match = _COLUMN_RE.search(message)
    if not match:
        return message, None
    return message[: match.start()], int(match.group(1))


def _clamp_end(column: int, end_column: int | None) -> int:
    if end_column is None or end_column <= column:
        return column + 1
    return end_column


def _first_token_span(raw: str) -> tuple[int, int]:
    stripped = raw.lstrip(' ')
    if not stripped:
        return 1, 2
    start = raw.find(stripped) + 1
    token = stripped.split(None, 1)[0]
    return start, start + max(len(token), 1)


def _parse_error_hint(message: str) -> str:
    upper = message.upper()
    if upper.startswith('UNKNOWN COMMAND'):
        return 'Use a supported DuckyScript command, key combo, or function call.'
    if upper.startswith('MISSING END_'):
        return 'Close the current block with the matching END_* terminator.'
    if 'UNTERMINATED STRING LITERAL' in upper:
        return 'Close the quote before the end of the line.'
    if 'REQUIRES AN EXPRESSION' in upper or 'INVALID EXPRESSION' in upper:
        return 'Check operators, parentheses, and variable names in this expression.'
    if upper.startswith('UNEXPECTED '):
        return 'This block terminator appears before the matching block start.'
    if 'INVALID ASSIGNMENT SYNTAX' in upper:
        return 'Assignments must target a $variable and include an expression.'
    return 'Review the highlighted line and nearby block structure.'


def _parse_error_diagnostic(
    exc: DuckyScriptError,
    lines_by_no: dict[int, object],
) -> dict[str, object]:
    message, column = _strip_column_suffix(exc.message)
    line = lines_by_no.get(exc.line_no)
    if line is None:
        start_column = column or 1
        end_column = _clamp_end(start_column, None)
    elif column is None:
        start_column, end_column = _first_token_span(line.raw)
    else:
        start_column = column
        end_column = _clamp_end(start_column, None)

    return {
        'code': 'parse_error',
        'end_column': end_column,
        'hint': _parse_error_hint(message),
        'line': exc.line_no,
        'message': message,
        'severity': 'error',
        'column': start_column,
    }


def _unsafe_variable_hint(allow_unsafe: bool) -> str:
    if allow_unsafe:
        return 'This internal reflects host state. Review it carefully before running.'
    return 'Turn on unsafe mode or remove this host-state dependent internal.'


def _unsafe_command_hint(allow_unsafe: bool) -> str:
    if allow_unsafe:
        return 'This command can affect host state or device behavior. Review it carefully.'
    return 'Turn on unsafe mode or remove this command before saving or running.'


def _unsafe_variable_hits(
    text: str,
    *,
    line_no: int,
    allow_unsafe: bool,
) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    index = 0

    while index < len(text):
        if text[index] != '$':
            index += 1
            continue

        if index + 1 < len(text) and text[index + 1] == '$':
            index += 2
            continue

        start = index + 1
        if start >= len(text) or not (text[start].isalpha() or text[start] == '_'):
            index += 1
            continue

        end = start + 1
        while end < len(text) and (text[end].isalnum() or text[end] == '_'):
            end += 1

        name = text[start:end]
        if name in UNSAFE_INTERNALS or name.startswith(_UNSAFE_INTERNAL_PREFIXES):
            severity = 'warning' if allow_unsafe else 'error'
            hits.append(
                {
                    'code': 'unsafe_internal',
                    'end_column': end + 1,
                    'hint': _unsafe_variable_hint(allow_unsafe),
                    'line': line_no,
                    'message': f'${name} is gated behind unsafe mode.',
                    'severity': severity,
                    'column': index + 1,
                    'command': f'${name}',
                    'allowed': allow_unsafe,
                }
            )

        index = end

    return hits


def _unsafe_hits(script: str, *, allow_unsafe: bool) -> list[dict[str, object]]:
    lines = lex_script(script)
    hits: list[dict[str, object]] = []
    multiline_end = ''

    for line in lines:
        if line.is_blank or line.is_comment:
            continue

        if multiline_end:
            if line.upper == multiline_end:
                multiline_end = ''
                continue
            hits.extend(
                _unsafe_variable_hits(
                    line.raw,
                    line_no=line.line_no,
                    allow_unsafe=allow_unsafe,
                )
            )
            continue

        multiline_end = _MULTILINE_ENDINGS.get(line.upper, '')
        if multiline_end:
            continue

        if line.keyword in UNSAFE_COMMANDS:
            start_column, end_column = _first_token_span(line.raw)
            severity = 'warning' if allow_unsafe else 'error'
            hits.append(
                {
                    'code': 'unsafe_command',
                    'end_column': end_column,
                    'hint': _unsafe_command_hint(allow_unsafe),
                    'line': line.line_no,
                    'message': f'{line.keyword} is gated behind unsafe mode.',
                    'severity': severity,
                    'column': start_column,
                    'command': line.keyword,
                    'allowed': allow_unsafe,
                }
            )

        hits.extend(
            _unsafe_variable_hits(
                line.raw,
                line_no=line.line_no,
                allow_unsafe=allow_unsafe,
            )
        )

    return hits


def _preview(text: str, *, multiline: bool = False) -> str:
    if multiline:
        first = text.split('\n', 1)[0]
        if not first.strip():
            return '<multiline>'
        text = first
    text = text.strip()
    if not text:
        return ''
    if len(text) > 48:
        return text[:45] + '...'
    return text


def _command_entry(stmt: dict[str, object], depth: int) -> dict[str, object]:
    kind = stmt['kind']
    line_no = int(stmt['line_no'])

    if kind == 'command':
        label = str(stmt['command'])
        detail = _preview(str(stmt['argument']))
    elif kind == 'assign':
        label = 'ASSIGN'
        detail = f"${stmt['name']} {stmt['operator']} {stmt['expression']}"
    elif kind == 'if':
        label = 'IF'
        detail = _preview(str(stmt['branches'][0]['condition']))
    elif kind == 'while':
        label = 'WHILE'
        detail = _preview(str(stmt['condition']))
    elif kind == 'function':
        label = 'FUNCTION'
        detail = f"{stmt['name']}()"
    elif kind == 'extension':
        label = 'EXTENSION'
        detail = str(stmt['name'])
    elif kind == 'button':
        label = 'BUTTON_DEF'
        detail = ''
    elif kind == 'string':
        label = 'STRINGLN' if stmt['newline'] else 'STRING'
        detail = _preview(str(stmt['text']))
    elif kind == 'string_block':
        label = 'STRINGLN' if stmt['newline'] else 'STRING'
        detail = _preview(str(stmt['text']), multiline=True)
    elif kind == 'random_char':
        label = str(stmt['command'])
        detail = ''
    elif kind == 'random_char_from':
        label = 'RANDOM_CHAR_FROM'
        detail = _preview(str(stmt['argument']))
    elif kind == 'repeat':
        label = 'REPEAT'
        detail = str(stmt['expression'])
    elif kind == 'return':
        label = 'RETURN'
        detail = _preview(str(stmt['expression']))
    elif kind == 'call':
        label = 'CALL'
        detail = f"{stmt['name']}()"
    elif kind == 'hold':
        label = 'HOLD'
        detail = str(stmt['combo'])
    elif kind == 'release':
        label = 'RELEASE'
        detail = str(stmt['combo'])
    elif kind == 'combo':
        label = 'COMBO'
        detail = str(stmt['combo'])
    elif kind == 'led':
        label = str(stmt['color'])
        detail = 'on' if stmt['enabled'] else 'off'
    else:
        label = str(kind).upper()
        detail = ''

    return {
        'depth': depth,
        'detail': detail,
        'kind': kind,
        'label': label,
        'line': line_no,
    }


def _collect_commands(
    statements: list[dict[str, object]],
    *,
    commands: list[dict[str, object]],
    depth: int = 0,
) -> None:
    for stmt in statements:
        commands.append(_command_entry(stmt, depth))

        if stmt['kind'] == 'if':
            for branch in stmt['branches']:
                _collect_commands(branch['body'], commands=commands, depth=depth + 1)
            _collect_commands(stmt['else_body'], commands=commands, depth=depth + 1)
            continue

        for child_key in ('body',):
            child = stmt.get(child_key)
            if isinstance(child, list):
                _collect_commands(child, commands=commands, depth=depth + 1)


def _summary(*, errors: int, warnings: int, commands: int) -> tuple[str, str]:
    if errors:
        noun = 'error' if errors == 1 else 'errors'
        return f'Fix {errors} {noun} before saving or running.', 'error'
    if warnings:
        noun = 'warning' if warnings == 1 else 'warnings'
        return f'Dry run passed with {warnings} {noun}.', 'warning'
    if commands:
        return f'Dry run passed for {commands} parsed commands.', 'success'
    return 'Dry run passed. No executable commands parsed yet.', 'success'


def _detail(*, errors: int, warnings: int) -> str:
    if errors:
        return 'Saving and running stay disabled until the highlighted issues are fixed.'
    if warnings:
        return 'Warnings are highlighted for review, but this script can still be saved and run.'
    return 'No blocking issues detected. Save and run are available.'


def _counts_label(*, commands: int, errors: int, warnings: int, unsafe: int) -> str:
    parts = [f'{commands} commands']
    if errors:
        parts.append(f'{errors} errors')
    elif warnings:
        parts.append(f'{warnings} warnings')
    if unsafe:
        parts.append(f'{unsafe} unsafe')
    return ' · '.join(parts)


def _badge(*, errors: int, warnings: int) -> tuple[str, str]:
    if errors:
        return 'Blocked', 'error'
    if warnings:
        return 'Warnings', 'warning'
    return 'Ready', 'success'


def analyze_script(script: str, *, allow_unsafe: bool) -> dict[str, object]:
    normalized = script.replace('\r\n', '\n').replace('\r', '\n')
    line_total = _line_count(normalized)

    try:
        lexed_lines = lex_script(normalized)
    except DuckyScriptError as exc:
        diagnostics = [_parse_error_diagnostic(exc, {})]
        summary, notice = _summary(errors=1, warnings=0, commands=0)
        detail = _detail(errors=1, warnings=0)
        badge_label, badge_tone = _badge(errors=1, warnings=0)
        return {
            'badge_label': badge_label,
            'badge_tone': badge_tone,
            'blocking': True,
            'can_run': False,
            'can_save': False,
            'command_count': 0,
            'counts_label': _counts_label(commands=0, errors=1, warnings=0, unsafe=0),
            'diagnostics': diagnostics,
            'detail': detail,
            'error_count': 1,
            'line_count': line_total,
            'notice': notice,
            'parsed_commands': [],
            'summary': summary,
            'unsafe_commands': [],
            'unsafe_count': 0,
            'warning_count': 0,
        }

    lines_by_no = {line.line_no: line for line in lexed_lines}

    try:
        statements = parse_script(normalized)
    except DuckyScriptError as exc:
        diagnostics = [_parse_error_diagnostic(exc, lines_by_no)]
        summary, notice = _summary(errors=1, warnings=0, commands=0)
        detail = _detail(errors=1, warnings=0)
        badge_label, badge_tone = _badge(errors=1, warnings=0)
        return {
            'badge_label': badge_label,
            'badge_tone': badge_tone,
            'blocking': True,
            'can_run': False,
            'can_save': False,
            'command_count': 0,
            'counts_label': _counts_label(commands=0, errors=1, warnings=0, unsafe=0),
            'diagnostics': diagnostics,
            'detail': detail,
            'error_count': 1,
            'line_count': line_total,
            'notice': notice,
            'parsed_commands': [],
            'summary': summary,
            'unsafe_commands': [],
            'unsafe_count': 0,
            'warning_count': 0,
        }

    parsed_commands: list[dict[str, object]] = []
    _collect_commands(statements, commands=parsed_commands)

    unsafe_hits = _unsafe_hits(normalized, allow_unsafe=allow_unsafe)
    diagnostics = [
        {
            'code': hit['code'],
            'column': hit['column'],
            'end_column': hit['end_column'],
            'hint': hit['hint'],
            'line': hit['line'],
            'message': hit['message'],
            'severity': hit['severity'],
        }
        for hit in unsafe_hits
    ]
    unsafe_commands = [
        {
            'allowed': hit['allowed'],
            'command': hit['command'],
            'hint': hit['hint'],
            'line': hit['line'],
            'message': hit['message'],
            'severity': hit['severity'],
        }
        for hit in unsafe_hits
    ]
    error_count = sum(1 for diag in diagnostics if diag['severity'] == 'error')
    warning_count = sum(1 for diag in diagnostics if diag['severity'] == 'warning')
    summary, notice = _summary(
        errors=error_count,
        warnings=warning_count,
        commands=len(parsed_commands),
    )
    detail = _detail(errors=error_count, warnings=warning_count)
    badge_label, badge_tone = _badge(errors=error_count, warnings=warning_count)

    return {
        'badge_label': badge_label,
        'badge_tone': badge_tone,
        'blocking': error_count > 0,
        'can_run': error_count == 0,
        'can_save': error_count == 0,
        'command_count': len(parsed_commands),
        'counts_label': _counts_label(
            commands=len(parsed_commands),
            errors=error_count,
            warnings=warning_count,
            unsafe=len(unsafe_commands),
        ),
        'diagnostics': diagnostics,
        'detail': detail,
        'error_count': error_count,
        'line_count': line_total,
        'notice': notice,
        'parsed_commands': parsed_commands,
        'summary': summary,
        'unsafe_commands': unsafe_commands,
        'unsafe_count': len(unsafe_commands),
        'warning_count': warning_count,
    }
