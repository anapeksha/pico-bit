import type { Diagnostic, ValidationState } from '../api/contracts';

const HL_FLOW = new Set([
  'IF',
  'ELSE',
  'ELSEIF',
  'END_IF',
  'WHILE',
  'END_WHILE',
  'FUNCTION',
  'END_FUNCTION',
  'RETURN',
  'CALL',
  'REPEAT',
  'DEFINE',
  'BUTTON_DEF',
  'END_BUTTON',
  'EXTENSION',
  'END_EXTENSION',
]);
const HL_STRING_CMD = new Set(['STRING', 'STRINGLN', 'END_STRING', 'END_STRINGLN']);
const HL_ASSIGNMENT = new Set(['VAR', 'DEFINE', '$_DEFINE']);
const HL_KEYWORD = new Set([
  'ATTACKMODE',
  'DELAY',
  'DEFAULTDELAY',
  'DEFAULT_DELAY',
  'DEFAULTCHARDELAY',
  'DEFAULT_CHAR_DELAY',
  'DEFAULTCHARJITTER',
  'DISABLE_BUTTON',
  'ENABLE_BUTTON',
  'EXFIL',
  'HIDE_PAYLOAD',
  'INJECT_MOD',
  'INJECT_VAR',
  'RD_KBD',
  'RELEASE',
  'RESET',
  'RESTORE_ATTACKMODE',
  'RESTORE_HOST_KEYBOARD_LOCK_STATE',
  'RESTORE_PAYLOAD',
  'RESTART_PAYLOAD',
  'SAVE_ATTACKMODE',
  'SAVE_HOST_KEYBOARD_LOCK_STATE',
  'STOP_PAYLOAD',
  'VERSION',
  'WAIT_FOR_BUTTON_PRESS',
  'WAIT_FOR_CAPS_CHANGE',
  'WAIT_FOR_CAPS_OFF',
  'WAIT_FOR_CAPS_ON',
  'WAIT_FOR_NUM_CHANGE',
  'WAIT_FOR_NUM_OFF',
  'WAIT_FOR_NUM_ON',
  'WAIT_FOR_SCROLL_CHANGE',
  'WAIT_FOR_SCROLL_OFF',
  'WAIT_FOR_SCROLL_ON',
  'RANDOM_CHAR',
  'RANDOM_CHAR_FROM',
  'RANDOM_LOWERCASE_LETTER',
  'RANDOM_UPPERCASE_LETTER',
  'RANDOM_LETTER',
  'RANDOM_NUMBER',
  'RANDOM_SPECIAL',
  'HOLD',
  'LED_R',
  'LED_G',
  'LED_B',
  'LED_ON',
  'LED_OFF',
  'WAIT_FOR_STORAGE',
  'SAVE_STORAGE',
  'RESTORE_STORAGE',
]);
const HL_MODIFIER = new Set([
  'CTRL',
  'CONTROL',
  'SHIFT',
  'ALT',
  'GUI',
  'WINDOWS',
  'COMMAND',
  'OPTION',
  'LEFT_CTRL',
  'LEFT_CONTROL',
  'RIGHT_CTRL',
  'RIGHT_CONTROL',
  'LEFT_SHIFT',
  'RIGHT_SHIFT',
  'LEFT_ALT',
  'RIGHT_ALT',
  'LEFT_GUI',
  'RIGHT_GUI',
]);
const HL_KEY = new Set([
  'ENTER',
  'ESC',
  'ESCAPE',
  'SPACE',
  'TAB',
  'BACKSPACE',
  'DELETE',
  'INSERT',
  'HOME',
  'END',
  'PAGEUP',
  'PAGEDOWN',
  'UP',
  'DOWN',
  'LEFT',
  'RIGHT',
  'CAPSLOCK',
  'NUMLOCK',
  'SCROLLLOCK',
  'PRINTSCREEN',
  'PAUSE',
  'MENU',
]);
for (let index = 1; index <= 24; index += 1) HL_KEY.add(`F${index}`);

const INLINE_TOKEN_PATTERN =
  /\$[A-Za-z_]\w*|0x[\da-f]+|\d+|\+=|-=|\*=|\/=|%=|==|!=|<=|>=|&&|\|\||[=+\-*/%<>!]|\b[A-Z][A-Z0-9_]*\b/gi;

export type EditorMetrics = {
  charWidth: number;
  lineHeight: number;
  padLeft: number;
  padTop: number;
};

export type Marker = {
  line: number;
  severity: Diagnostic['severity'];
  style: string;
  title: string;
};

export type GutterLine = {
  line: number;
  severity?: Diagnostic['severity'];
  title?: string;
};

export const DEFAULT_EDITOR_METRICS: EditorMetrics = {
  charWidth: 8,
  lineHeight: 22.1,
  padLeft: 16,
  padTop: 14,
};

export function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function highlightInline(value: string): string {
  let output = '';
  let cursor = 0;

  for (const match of value.matchAll(INLINE_TOKEN_PATTERN)) {
    const token = match[0];
    const index = match.index || 0;

    output += escapeHtml(value.slice(cursor, index));
    output += highlightToken(token);
    cursor = index + token.length;
  }

  output += escapeHtml(value.slice(cursor));
  return output;
}

function highlightToken(token: string): string {
  const upper = token.toUpperCase();

  if (token.startsWith('$')) return `<span class="hl-var">${escapeHtml(token)}</span>`;
  if (/^(?:0x[\da-f]+|\d+)$/i.test(token)) {
    return `<span class="hl-number">${escapeHtml(token)}</span>`;
  }
  if (/^(?:\+=|-=|\*=|\/=|%=|==|!=|<=|>=|&&|\|\||[=+\-*/%<>!])$/.test(token)) {
    return `<span class="hl-operator">${escapeHtml(token)}</span>`;
  }
  if (['TRUE', 'FALSE', 'NULL', 'ENABLE', 'DISABLE', 'ENABLED', 'DISABLED'].includes(upper)) {
    return `<span class="hl-constant">${escapeHtml(token)}</span>`;
  }
  if (HL_MODIFIER.has(upper)) return `<span class="hl-modifier">${escapeHtml(token)}</span>`;
  if (HL_KEY.has(upper)) return `<span class="hl-key">${escapeHtml(token)}</span>`;

  return escapeHtml(token);
}

function splitTrailingComment(value: string): [string, string] {
  const marker = value.search(/\sREM(?:\s|$)/i);
  if (marker < 0) return [value, ''];
  return [value.slice(0, marker), value.slice(marker)];
}

function highlightLine(raw: string): string {
  if (!raw.trim()) return escapeHtml(raw);
  const indent = raw.length - raw.trimStart().length;
  const stripped = raw.slice(indent);
  const upper = stripped.toUpperCase();
  if (upper === 'REM' || upper.startsWith('REM ')) {
    return `<span class="hl-comment">${escapeHtml(raw)}</span>`;
  }

  const spaceAt = stripped.search(/\s/);
  const token = spaceAt < 0 ? stripped : stripped.slice(0, spaceAt);
  const rest = spaceAt < 0 ? '' : stripped.slice(spaceAt);
  const tokenUpper = token.toUpperCase();
  let className = '';
  if (HL_ASSIGNMENT.has(tokenUpper)) className = 'hl-assign';
  else if (HL_FLOW.has(tokenUpper)) className = 'hl-flow';
  else if (HL_STRING_CMD.has(tokenUpper) || HL_KEYWORD.has(tokenUpper)) {
    className = 'hl-keyword';
  } else if (HL_MODIFIER.has(tokenUpper)) {
    className = 'hl-modifier';
  } else if (HL_KEY.has(tokenUpper)) {
    className = 'hl-key';
  }
  if (!className) return highlightInline(raw);

  const indentHtml = escapeHtml(raw.slice(0, indent));
  const tokenHtml = `<span class="${className}">${escapeHtml(token)}</span>`;
  const [codeRest, commentRest] = splitTrailingComment(rest);
  const restHtml = HL_STRING_CMD.has(tokenUpper)
    ? `<span class="hl-string">${highlightInline(codeRest)}</span>`
    : highlightInline(codeRest);
  const commentHtml = commentRest
    ? `<span class="hl-comment">${escapeHtml(commentRest)}</span>`
    : '';
  return indentHtml + tokenHtml + restHtml + commentHtml;
}

export function highlightPayload(payload: string): string {
  return payload.split('\n').map(highlightLine).join('\n');
}

export function diagnosticsByLine(diagnostics: Diagnostic[] = []): Map<number, Diagnostic> {
  const byLine = new Map<number, Diagnostic>();
  for (const diagnostic of diagnostics) {
    if (!byLine.has(diagnostic.line) || diagnostic.severity === 'error') {
      byLine.set(diagnostic.line, diagnostic);
    }
  }
  return byLine;
}

export function gutterLines(payload: string, validation: ValidationState | null): GutterLine[] {
  const lines = Math.max(1, payload.split('\n').length);
  const byLine = diagnosticsByLine(validation?.diagnostics || []);
  return Array.from({ length: lines }, (_, index) => {
    const line = index + 1;
    const diagnostic = byLine.get(line);
    return {
      line,
      severity: diagnostic?.severity,
      title: diagnostic?.message,
    };
  });
}

export function editorMarkers(
  validation: ValidationState | null,
  metrics: EditorMetrics,
  scrollLeft: number,
  scrollTop: number,
): Marker[] {
  return (validation?.diagnostics || []).map((diagnostic) => {
    const column = Math.max(1, diagnostic.column || 1);
    const endColumn = Math.max(column + 1, diagnostic.end_column || column + 8);
    const left = metrics.padLeft + (column - 1) * metrics.charWidth - scrollLeft;
    const width = Math.max(10, (endColumn - column) * metrics.charWidth);
    const top = metrics.padTop + (diagnostic.line - 1) * metrics.lineHeight - scrollTop;
    return {
      line: diagnostic.line,
      severity: diagnostic.severity,
      style: `left:${left}px;top:${top + metrics.lineHeight - 2}px;width:${width}px;`,
      title: diagnostic.message,
    };
  });
}
