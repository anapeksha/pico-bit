/**
 * Keyboard / HID typing-target state.
 *
 * The device remembers the active OS and layout selection across reboots.
 * `keyboard` holds the full state returned by the server.
 * `keyboardReady` tracks whether the HID stack has been initialised on the device.
 * `changeKeyboardTarget` sends a POST to update the selection and applies the
 * response immediately so the UI reflects the new target without a page reload.
 */
import { derived, writable } from 'svelte/store';

import { requestJson } from '../lib/api';
import type { KeyboardState } from '../lib/types';
import { showNotice } from './ui';

/** Fallback keyboard state used before the bootstrap response arrives. */
export const defaultKeyboard: KeyboardState = {
  hint: 'Used for typed text and remembered on the device.',
  layout: 'US',
  layoutLabel: 'English (US)',
  layouts: [{ code: 'US', label: 'English (US)' }],
  os: 'WIN',
  osLabel: 'Windows',
  oses: [{ code: 'WIN', label: 'Windows' }],
  targetLabel: 'Windows · English (US)',
};

/** `true` once the device HID stack is ready to type. */
export const keyboardReady = writable(false);

/** Active keyboard layout and OS selection. */
export const keyboard = writable<KeyboardState>(defaultKeyboard);

/** `'Ready'` when the HID stack is initialised, `'Waiting'` otherwise. */
export const hidState = derived(keyboardReady, ($ready) => ($ready ? 'Ready' : 'Waiting'));

/**
 * Apply a keyboard state snapshot from any server response that includes
 * keyboard fields (bootstrap, layout-change response, error payloads).
 */
export function applyKeyboardState(data: Record<string, any>) {
  keyboard.set({
    hint: data.keyboard_layout_hint || defaultKeyboard.hint,
    layout: data.keyboard_layout || defaultKeyboard.layout,
    layoutLabel: data.keyboard_layout_label || defaultKeyboard.layoutLabel,
    layouts: data.keyboard_layouts || defaultKeyboard.layouts,
    os: data.keyboard_os || defaultKeyboard.os,
    osLabel: data.keyboard_os_label || defaultKeyboard.osLabel,
    oses: data.keyboard_oses || defaultKeyboard.oses,
    targetLabel: data.keyboard_target_label || defaultKeyboard.targetLabel,
  });
}

/**
 * POST a new OS and/or layout selection to the device and apply the response.
 * On error the server may return a partial state which is applied anyway so
 * the UI stays in sync with the device.
 */
export async function changeKeyboardTarget(next: { layout?: string; os?: string }) {
  try {
    const data = await requestJson<Record<string, any>>('/api/keyboard-layout', {
      method: 'POST',
      body: JSON.stringify(next),
    });
    applyKeyboardState(data);
    showNotice(data.message || 'Typing target updated.', data.notice || 'success');
  } catch (error: any) {
    if (error.data) applyKeyboardState(error.data);
    showNotice(error.message, 'error');
  }
}
