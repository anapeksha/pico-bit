import { describe, expect, it } from 'vitest';

import { highlightPayload } from './editor';

describe('highlightPayload', () => {
  it('highlights flow, assignment, variables, operators, numbers, and keys', () => {
    const html = highlightPayload('IF $count >= 3\nVAR $count = 0\nCTRL ALT DELETE');

    expect(html).toContain('<span class="hl-flow">IF</span>');
    expect(html).toContain('<span class="hl-var">$count</span>');
    expect(html).toContain('<span class="hl-operator">&gt;=</span>');
    expect(html).toContain('<span class="hl-number">3</span>');
    expect(html).toContain('<span class="hl-assign">VAR</span>');
    expect(html).toContain('<span class="hl-modifier">CTRL</span>');
    expect(html).toContain('<span class="hl-modifier">ALT</span>');
    expect(html).toContain('<span class="hl-key">DELETE</span>');
  });

  it('keeps string bodies distinct while highlighting embedded variables', () => {
    const html = highlightPayload('STRING Hello $name');

    expect(html).toContain('<span class="hl-keyword">STRING</span>');
    expect(html).toContain(
      '<span class="hl-string"> Hello <span class="hl-var">$name</span></span>',
    );
  });

  it('escapes HTML and highlights trailing comments', () => {
    const html = highlightPayload('DELAY 100 REM <wait>');

    expect(html).toContain('<span class="hl-keyword">DELAY</span>');
    expect(html).toContain('<span class="hl-number">100</span>');
    expect(html).toContain('<span class="hl-comment"> REM &lt;wait&gt;</span>');
    expect(html).not.toContain('<wait>');
  });
});
