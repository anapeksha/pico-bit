import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const BOOTSTRAP_KEYBOARD = {
  keyboard_layout: 'US',
  keyboard_os: 'WIN',
};

const TARGET_KEY = 'picobit.keyboard.target.v1';

describe('keyboard store', () => {
  beforeEach(() => {
    localStorage.clear();
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

  it('falls back to Windows US when no frontend storage exists', async () => {
    const { applyKeyboardState, keyboard } = await import('./keyboard');

    applyKeyboardState(BOOTSTRAP_KEYBOARD);

    expect(get(keyboard)).toMatchObject({
      layout: 'US',
      os: 'WIN',
      targetLabel: 'Windows - English (US)',
    });
  });

  it('restores a saved macOS US target from frontend storage', async () => {
    localStorage.setItem(TARGET_KEY, JSON.stringify({ layout: 'US', os: 'MAC' }));

    const { applyKeyboardState, keyboard } = await import('./keyboard');

    applyKeyboardState(BOOTSTRAP_KEYBOARD);

    expect(get(keyboard)).toMatchObject({
      layout: 'US',
      os: 'MAC',
      targetLabel: 'macOS - English (US)',
    });
  });

  it('persists target changes locally and syncs firmware', async () => {
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

    expect(JSON.parse(localStorage.getItem(TARGET_KEY) || '{}')).toEqual({
      layout: 'DE',
      os: 'LINUX',
    });
    expect(fetch).toHaveBeenCalledWith('/api/keyboard-layout', {
      body: JSON.stringify({ layout: 'DE', os: 'LINUX' }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  });
});
