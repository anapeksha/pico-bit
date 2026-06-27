/**
 * Keyboard / HID typing-target state.
 *
 * Bootstrap provides the available OS/layout options and Host HID status.
 * The selected target profile is a frontend preference stored in localStorage,
 * so changing it never burns flash or calls a firmware mutation endpoint.
 */
import { derived, get, writable } from 'svelte/store';

import type {
  BootstrapState,
  HostHidState,
  KeyboardProfile,
  KeyboardState,
  KeyboardTargetRequest,
  SelectOption,
} from '../api/contracts';
import { showNotice } from './ui';

type KeyboardStateSource = Partial<BootstrapState>;
type StoredKeyboardTarget = KeyboardTargetRequest & { profileId?: string };

const KEYBOARD_TARGET_STORAGE_KEY = 'picobit.keyboard.target.v1';
const KEYBOARD_PROFILES_STORAGE_KEY = 'picobit.keyboard.profiles.v1';
const CUSTOM_PROFILE_ID = 'custom';

export const DEFAULT_KEYBOARD_PROFILES: KeyboardProfile[] = [
  { id: 'windows-us', label: 'Windows US', os: 'WIN', layout: 'US' },
  { id: 'macos-us', label: 'macOS US', os: 'MAC', layout: 'US' },
  { id: 'linux-us', label: 'Linux US', os: 'LINUX', layout: 'US' },
];

/** Fallback keyboard state used before the bootstrap response arrives. */
export const defaultKeyboard: KeyboardState = {
  hint: 'Used for typed text and remembered in this browser.',
  layout: 'US',
  layoutLabel: 'English (US)',
  layouts: [{ code: 'US', label: 'English (US)' }],
  os: 'WIN',
  osLabel: 'Windows',
  oses: [
    { code: 'WIN', label: 'Windows' },
    { code: 'MAC', label: 'macOS' },
    { code: 'LINUX', label: 'Linux' },
  ],
  targetLabel: 'Windows - English (US)',
};

/** `true` once the device HID stack is ready to type. */
export const keyboardReady = writable(false);

/** Host HID transport state reported by bootstrap. */
export const hostHid = writable<HostHidState>({
  active: false,
  available: false,
  message: 'Waiting',
  state: 'inactive',
});

/** Saved OS/layout target profiles. */
export const keyboardProfiles = writable<KeyboardProfile[]>(loadKeyboardProfiles());

/** Active profile id; `custom` means OS/layout no longer matches a saved preset. */
export const selectedKeyboardProfileId = writable(loadKeyboardTarget()?.profileId || 'windows-us');

/** Active keyboard layout and OS selection. */
export const keyboard = writable<KeyboardState>(defaultKeyboard);

/** Human-readable Host HID state. */
export const hidState = derived(hostHid, ($hostHid) => {
  if (!$hostHid.available) return 'Unavailable';
  if ($hostHid.active || $hostHid.state === 'active') return 'Ready';
  if ($hostHid.state === 'error') return 'Error';
  return 'Waiting';
});

function browserStorage(): Storage | null {
  return typeof localStorage === 'undefined' ? null : localStorage;
}

function loadKeyboardProfiles(): KeyboardProfile[] {
  const storage = browserStorage();
  if (!storage) return DEFAULT_KEYBOARD_PROFILES;

  try {
    const raw = storage.getItem(KEYBOARD_PROFILES_STORAGE_KEY);
    if (!raw) return DEFAULT_KEYBOARD_PROFILES;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return DEFAULT_KEYBOARD_PROFILES;
    const profiles = parsed.filter(isKeyboardProfile);
    return profiles.length ? profiles : DEFAULT_KEYBOARD_PROFILES;
  } catch {
    return DEFAULT_KEYBOARD_PROFILES;
  }
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
      profileId: typeof target.profileId === 'string' ? target.profileId : undefined,
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

function isKeyboardProfile(value: unknown): value is KeyboardProfile {
  if (!value || typeof value !== 'object') return false;
  const profile = value as Record<string, unknown>;
  return (
    typeof profile.id === 'string' &&
    typeof profile.label === 'string' &&
    typeof profile.layout === 'string' &&
    typeof profile.os === 'string'
  );
}

function optionLabel(options: SelectOption[], code: string, fallback: string) {
  return options.find((option) => option.code === code)?.label || fallback;
}

function findProfileId(profiles: KeyboardProfile[], os: string, layout: string) {
  return profiles.find((profile) => profile.os === os && profile.layout === layout)?.id;
}

function hasProfile(profiles: KeyboardProfile[], id: string) {
  return profiles.some((profile) => profile.id === id);
}

function targetFromStorageOrDefault() {
  const stored = loadKeyboardTarget();
  return {
    layout: stored?.layout || defaultKeyboard.layout,
    os: stored?.os || defaultKeyboard.os,
    profileId: stored?.profileId,
  };
}

export function applyHostHidState(state?: HostHidState, fallbackReady = false) {
  const next = state || {
    active: fallbackReady,
    available: fallbackReady,
    message: fallbackReady ? 'Host HID interface is available.' : 'Waiting',
    state: fallbackReady ? 'active' : 'inactive',
  };

  hostHid.set(next);
  keyboardReady.set(Boolean(next.active || next.state === 'active'));
}

/**
 * Apply available keyboard options from bootstrap. The active target is kept as
 * a browser preference and falls back to Windows US when storage is absent.
 */
export function applyKeyboardState(data: KeyboardStateSource) {
  const profiles = loadKeyboardProfiles();
  const storedTarget = targetFromStorageOrDefault();
  const layouts = data.keyboard_layouts || defaultKeyboard.layouts;
  const oses = data.keyboard_oses || defaultKeyboard.oses;
  const layout = storedTarget.layout;
  const os = storedTarget.os;
  const layoutLabel = optionLabel(layouts, layout, defaultKeyboard.layoutLabel);
  const osLabel = optionLabel(oses, os, defaultKeyboard.osLabel);
  const matchedProfile = findProfileId(profiles, os, layout);

  keyboardProfiles.set(profiles);
  selectedKeyboardProfileId.set(
    storedTarget.profileId && hasProfile(profiles, storedTarget.profileId)
      ? storedTarget.profileId
      : matchedProfile || CUSTOM_PROFILE_ID,
  );
  keyboard.set({
    hint: data.keyboard_layout_hint || defaultKeyboard.hint,
    layout,
    layoutLabel,
    layouts,
    os,
    osLabel,
    oses,
    targetLabel: `${osLabel} - ${layoutLabel}`,
  });
}

function applyLocalKeyboardTarget(next: KeyboardTargetRequest, profileId?: string) {
  let savedTarget: StoredKeyboardTarget = {};

  keyboard.update((current) => {
    const layout = next.layout || current.layout;
    const os = next.os || current.os;
    const layoutLabel = optionLabel(current.layouts, layout, current.layoutLabel);
    const osLabel = optionLabel(current.oses, os, current.osLabel);
    const profiles = get(keyboardProfiles);
    const matchedProfile = profileId || findProfileId(profiles, os, layout) || CUSTOM_PROFILE_ID;

    selectedKeyboardProfileId.set(matchedProfile);
    savedTarget = { layout, os, profileId: matchedProfile };

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
  applyLocalKeyboardTarget(next);
  showNotice('Typing target saved locally.', 'success');
}

export function applyKeyboardProfile(profileId: string) {
  const profile = get(keyboardProfiles).find((item) => item.id === profileId);
  if (!profile) return;

  applyLocalKeyboardTarget(
    {
      layout: profile.layout,
      os: profile.os,
    },
    profile.id,
  );
  showNotice('Typing profile selected.', 'success');
}
