/**
 * Keyboard / HID typing-target state.
 *
 * Bootstrap provides the active OS/layout codes and Host HID status.
 * User changes are sent to firmware immediately; there is no browser-side restore.
 */
import { derived, writable } from 'svelte/store';

import { updateKeyboardTarget } from '../api/client';
import type {
  BootstrapState,
  HostHidState,
  KeyboardState,
  KeyboardTargetRequest,
  SelectOption,
} from '../api/contracts';
import { showNotice } from './ui';

type KeyboardStateSource = Partial<BootstrapState>;

const KEYBOARD_LAYOUTS: SelectOption[] = [
  { code: 'US', label: 'English (US)' },
  { code: 'UK', label: 'English (UK)' },
  { code: 'DE', label: 'German (DE)' },
  { code: 'FR', label: 'French (FR)' },
];
const KEYBOARD_OSES: SelectOption[] = [
  { code: 'WIN', label: 'Windows' },
  { code: 'MAC', label: 'macOS' },
  { code: 'LINUX', label: 'Linux' },
];

/** Fallback keyboard state used before the bootstrap response arrives. */
export const defaultKeyboard: KeyboardState = {
  hint: 'Used for typed text on the host.',
  layout: 'US',
  layoutLabel: 'English (US)',
  layouts: KEYBOARD_LAYOUTS,
  os: 'WIN',
  osLabel: 'Windows',
  oses: KEYBOARD_OSES,
  targetLabel: 'Windows - English (US)',
};

/** `true` once the device HID stack is ready to type. */
export const keyboardReady = writable(false);

/** Host HID transport state reported by bootstrap. */
export const hostHid = writable<HostHidState>({
  active: false,
});

/** Active keyboard layout and OS selection. */
export const keyboard = writable<KeyboardState>(defaultKeyboard);

/** Human-readable Host HID state. */
export const hidState = derived(hostHid, ($hostHid) => {
  return $hostHid.active ? 'Ready' : 'Waiting';
});

function optionLabel(options: SelectOption[], code: string, fallback: string) {
  return options.find((option) => option.code === code)?.label || fallback;
}

export function applyHostHidState(state?: HostHidState, fallbackReady = false) {
  const next = state || {
    active: fallbackReady,
  };

  hostHid.set(next);
  keyboardReady.set(Boolean(next.active));
}

export function applyKeyboardState(data: KeyboardStateSource) {
  const layouts = defaultKeyboard.layouts;
  const oses = defaultKeyboard.oses;
  const layout = data.keyboard_layout || defaultKeyboard.layout;
  const os = data.keyboard_os || defaultKeyboard.os;
  const layoutLabel = optionLabel(layouts, layout, defaultKeyboard.layoutLabel);
  const osLabel = optionLabel(oses, os, defaultKeyboard.osLabel);

  keyboard.set({
    hint: defaultKeyboard.hint,
    layout,
    layoutLabel,
    layouts,
    os,
    osLabel,
    oses,
    targetLabel: `${osLabel} - ${layoutLabel}`,
  });
}

function applyLocalKeyboardTarget(next: KeyboardTargetRequest) {
  keyboard.update((current) => {
    const layout = next.layout || current.layout;
    const os = next.os || current.os;
    const layoutLabel = optionLabel(current.layouts, layout, current.layoutLabel);
    const osLabel = optionLabel(current.oses, os, current.osLabel);

    return {
      ...current,
      layout,
      layoutLabel,
      os,
      osLabel,
      targetLabel: `${osLabel} - ${layoutLabel}`,
    };
  });
}

export async function changeKeyboardTarget(next: KeyboardTargetRequest) {
  let target: KeyboardTargetRequest = {};
  keyboard.update((current) => {
    target = {
      layout: next.layout || current.layout,
      os: next.os || current.os,
    };
    return current;
  });

  const response = await updateKeyboardTarget(target);
  applyLocalKeyboardTarget({
    layout: response.keyboard_layout || target.layout,
    os: response.keyboard_os || target.os,
  });
  showNotice(response.message || 'Typing target updated.', response.notice || 'success');
}
