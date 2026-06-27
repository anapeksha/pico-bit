import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const BOOTSTRAP_KEYBOARD = {
  keyboard_layout_hint: 'Local preference',
  keyboard_layouts: [{ code: 'US', label: 'English (US)' }],
  keyboard_oses: [
    { code: 'WIN', label: 'Windows' },
    { code: 'MAC', label: 'macOS' },
    { code: 'LINUX', label: 'Linux' },
  ],
};

const TARGET_KEY = 'picobit.keyboard.target.v1';

describe('keyboard store', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it('falls back to Windows US when no frontend storage exists', async () => {
    const { applyKeyboardState, keyboard, selectedKeyboardProfileId } = await import('./keyboard');

    applyKeyboardState(BOOTSTRAP_KEYBOARD);

    expect(get(keyboard)).toMatchObject({
      layout: 'US',
      os: 'WIN',
      targetLabel: 'Windows - English (US)',
    });
    expect(get(selectedKeyboardProfileId)).toBe('windows-us');
  });

  it('restores a saved macOS US profile from frontend storage', async () => {
    localStorage.setItem(
      TARGET_KEY,
      JSON.stringify({ layout: 'US', os: 'MAC', profileId: 'macos-us' }),
    );

    const { applyKeyboardState, keyboard, selectedKeyboardProfileId } = await import('./keyboard');

    applyKeyboardState(BOOTSTRAP_KEYBOARD);

    expect(get(keyboard)).toMatchObject({
      layout: 'US',
      os: 'MAC',
      targetLabel: 'macOS - English (US)',
    });
    expect(get(selectedKeyboardProfileId)).toBe('macos-us');
  });

  it('persists target changes locally without requiring a firmware mutation', async () => {
    const { applyKeyboardState, changeKeyboardTarget, selectedKeyboardProfileId } =
      await import('./keyboard');

    applyKeyboardState(BOOTSTRAP_KEYBOARD);
    await changeKeyboardTarget({ layout: 'US', os: 'LINUX' });

    expect(JSON.parse(localStorage.getItem(TARGET_KEY) || '{}')).toEqual({
      layout: 'US',
      os: 'LINUX',
      profileId: 'linux-us',
    });
    expect(get(selectedKeyboardProfileId)).toBe('linux-us');
  });
});
