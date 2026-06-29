import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const BOOTSTRAP_KEYBOARD = {
  keyboard_layout: 'US',
  keyboard_os: 'WIN',
};

describe('keyboard store', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          keyboard_layout: 'US',
          keyboard_os: 'WIN',
          message: 'Keyboard target updated.',
          notice: 'success',
        }),
      }),
    );
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('applies the firmware keyboard target from bootstrap without syncing', async () => {
    const { applyKeyboardState, keyboard } = await import('./keyboard');

    applyKeyboardState({
      keyboard_layout: 'US',
      keyboard_os: 'MAC',
    });

    expect(get(keyboard)).toMatchObject({
      layout: 'US',
      os: 'MAC',
      targetLabel: 'macOS - English (US)',
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it('falls back to Windows US when bootstrap omits target codes', async () => {
    const { applyKeyboardState, keyboard } = await import('./keyboard');

    applyKeyboardState({});

    expect(get(keyboard)).toMatchObject({
      layout: 'US',
      os: 'WIN',
      targetLabel: 'Windows - English (US)',
    });
  });

  it('syncs firmware once when the user changes target', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({
        keyboard_layout: 'DE',
        keyboard_os: 'LINUX',
        message: 'Keyboard target updated.',
        notice: 'success',
      }),
    } as unknown as Response);

    const { applyKeyboardState, changeKeyboardTarget } = await import('./keyboard');

    applyKeyboardState(BOOTSTRAP_KEYBOARD);
    await changeKeyboardTarget({ layout: 'DE', os: 'LINUX' });

    expect(fetch).toHaveBeenCalledWith('/api/keyboard/layout', {
      body: JSON.stringify({ layout: 'DE', os: 'LINUX' }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
