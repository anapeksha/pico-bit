/**
 * Keyboard / HID typing-target state.
 *
 * Bootstrap provides the available OS/layout options and Host HID status.
 * The selected OS/layout target is a frontend preference stored in localStorage,
 * and is also pushed into firmware RAM so DuckyScript STRING mapping changes immediately.
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
type StoredKeyboardTarget = KeyboardTargetRequest;

const KEYBOARD_TARGET_STORAGE_KEY = 'picobit.keyboard.target.v1';
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
let lastFirmwareSync = '';

/** Fallback keyboard state used before the bootstrap response arrives. */
export const defaultKeyboard: KeyboardState = {
  hint: 'Used for typed text and remembered in this browser.',
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

function browserStorage(): Storage | null {
  return typeof localStorage === 'undefined' ? null : localStorage;
}

function loadKeyboardTarget(): StoredKeyboardTarget | null {
  const storage = browserStorage();
  if (!storage) return null;

  try {
    const raw = storage.getItem(KEYBOARD_TARGET_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    const target = parsed as Record<string, unknown>;
    return {
      layout: typeof target.layout === 'string' ? target.layout : undefined,
      os: typeof target.os === 'string' ? target.os : undefined,
    };
  } catch {
    return null;
  }
}

function saveKeyboardTarget(target: StoredKeyboardTarget) {
  const storage = browserStorage();
  if (!storage) return;
  storage.setItem(KEYBOARD_TARGET_STORAGE_KEY, JSON.stringify(target));
}

function targetKey(target: StoredKeyboardTarget) {
  return `${target.os || ''}:${target.layout || ''}`;
}

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

/**
 * Apply available keyboard options from bootstrap. The active target is kept as
 * a browser preference and falls back to Windows US when storage is absent.
 */
export function applyKeyboardState(data: KeyboardStateSource) {
  const storedTarget = loadKeyboardTarget();
  const layouts = defaultKeyboard.layouts;
  const oses = defaultKeyboard.oses;
  const layout = storedTarget?.layout || data.keyboard_layout || defaultKeyboard.layout;
  const os = storedTarget?.os || data.keyboard_os || defaultKeyboard.os;
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

  if (storedTarget && targetKey(storedTarget) !== lastFirmwareSync) {
    const target = { layout, os };
    const key = targetKey(target);
    lastFirmwareSync = key;
    void updateKeyboardTarget(target).catch(() => {
      lastFirmwareSync = '';
    });
  }
}

function applyLocalKeyboardTarget(next: KeyboardTargetRequest) {
  let savedTarget: StoredKeyboardTarget = {};

  keyboard.update((current) => {
    const layout = next.layout || current.layout;
    const os = next.os || current.os;
    const layoutLabel = optionLabel(current.layouts, layout, current.layoutLabel);
    const osLabel = optionLabel(current.oses, os, current.osLabel);

    savedTarget = { layout, os };

    return {
      ...current,
      layout,
      layoutLabel,
      os,
      osLabel,
      targetLabel: `${osLabel} - ${layoutLabel}`,
    };
  });

  saveKeyboardTarget(savedTarget);
}

export async function changeKeyboardTarget(next: KeyboardTargetRequest) {
  let target: StoredKeyboardTarget = {};
  keyboard.update((current) => {
    target = {
      layout: next.layout || current.layout,
      os: next.os || current.os,
    };
    return current;
  });

  const response = await updateKeyboardTarget(target);
  lastFirmwareSync = targetKey(target);
  applyLocalKeyboardTarget({
    layout: response.keyboard_layout || target.layout,
    os: response.keyboard_os || target.os,
  });
  showNotice(response.message || 'Typing target updated.', response.notice || 'success');
}
