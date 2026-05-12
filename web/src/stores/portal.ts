import { derived, get, writable } from 'svelte/store';

import { requestJson, uploadBinaryFile } from '../lib/api';
import type {
  BootstrapState,
  KeyboardState,
  LootRecord,
  NoticeTone,
  RunHistoryItem,
  TargetOs,
  UsbAgentState,
  ValidationState,
} from '../lib/types';

const defaultKeyboard: KeyboardState = {
  hint: 'Used for typed text and remembered on the device.',
  layout: 'US',
  layoutLabel: 'English (US)',
  layouts: [{ code: 'US', label: 'English (US)' }],
  os: 'WIN',
  osLabel: 'Windows',
  oses: [{ code: 'WIN', label: 'Windows' }],
  targetLabel: 'Windows · English (US)',
};

let noticeTimer = 0;
let validationRequest = 0;
let lootStream: EventSource | null = null;

export const apSsid = writable('PicoBit');
export const apPassword = writable('Open network');
export const authEnabled = writable(false);
export const keyboardReady = writable(false);
export const hostUsb = writable<UsbAgentState>({
  available: false,
  message: 'Waiting',
  mounted: false,
  state: 'inactive',
});
export const seededThisBoot = writable(false);
export const keyboard = writable<KeyboardState>(defaultKeyboard);
export const payload = writable('');
export const payloadState = writable('Saved on device');
export const validation = writable<ValidationState | null>(null);
export const validating = writable(false);
export const saving = writable(false);
export const running = writable(false);
export const runHistory = writable<RunHistoryItem[]>([]);
export const notice = writable<{
  message: string;
  tone: NoticeTone;
  visible: boolean;
}>({
  message: '',
  tone: 'quiet',
  visible: false,
});
export const validationModalOpen = writable(false);
export const activeAccordion = writable<'ducky' | 'armory'>('ducky');
export const binaryTargetOs = writable<TargetOs>('windows');
export const hasBinary = writable(false);
export const stagedBinaryName = writable('');
export const uploadProgress = writable(0);
export const uploadingBinary = writable(false);
export const injectingBinary = writable(false);
export const armoryNotice = writable<{
  message: string;
  tone: NoticeTone;
  visible: boolean;
}>({
  message: '',
  tone: 'quiet',
  visible: false,
});
export const loot = writable<LootRecord | null>(null);
export const importingLoot = writable(false);

export const canSave = derived(
  [validation, validating, saving],
  ([$validation, $validating, $saving]) =>
    !$validating && !$saving && Boolean($validation?.can_save),
);
export const canRun = derived(
  [validation, validating, running],
  ([$validation, $validating, $running]) =>
    !$validating && !$running && Boolean($validation?.can_run),
);
export const hidState = derived(keyboardReady, ($ready) =>
  $ready ? 'Ready' : 'Waiting',
);
export const usbStateLabel = derived(hostUsb, ($usb) => {
  if (!$usb.available) return 'Unavailable';
  if ($usb.mounted || $usb.active || $usb.state === 'active') return 'Active';
  if ($usb.state === 'error') return 'Error';
  return 'Inactive';
});

export function showNotice(message: string, tone: NoticeTone = 'quiet') {
  window.clearTimeout(noticeTimer);
  if (!message) {
    notice.set({ message: '', tone: 'quiet', visible: false });
    return;
  }
  notice.set({ message, tone, visible: true });
  noticeTimer = window.setTimeout(() => {
    notice.set({ message: '', tone: 'quiet', visible: false });
  }, 2000);
}

function setArmoryNotice(message: string, tone: NoticeTone = 'quiet') {
  armoryNotice.set({ message, tone, visible: Boolean(message) });
}

function applyKeyboardState(data: Record<string, any>) {
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

function applyUsbAgent(state?: UsbAgentState) {
  if (state) hostUsb.set(state);
}

function applyBootstrap(data: BootstrapState) {
  apSsid.set(data.ap_ssid || 'PicoBit');
  apPassword.set(data.ap_password || 'Open network');
  authEnabled.set(Boolean(data.auth_enabled));
  keyboardReady.set(Boolean(data.keyboard_ready));
  seededThisBoot.set(Boolean(data.seeded));
  hasBinary.set(Boolean(data.has_binary));
  runHistory.set(data.run_history || []);
  payload.set(data.payload || '');
  payloadState.set(data.seeded ? 'Seeded on boot' : 'Saved on device');
  if (data.validation) validation.set(data.validation);
  applyKeyboardState(data);
  applyUsbAgent(data.usb_agent);
  if (data.usb_agent?.filename) stagedBinaryName.set(data.usb_agent.filename);
  if (data.message) showNotice(data.message, data.notice || 'quiet');
}

export async function loadBootstrap() {
  const data = await requestJson<BootstrapState>('/api/bootstrap');
  applyBootstrap(data);
  await loadLootSnapshot();
}

export async function validatePayloadDraft(script = get(payload)) {
  const requestId = ++validationRequest;
  validating.set(true);
  try {
    const data = await requestJson<{ validation: ValidationState }>(
      '/api/validate',
      {
        method: 'POST',
        body: JSON.stringify({ payload: script }),
      },
    );
    if (requestId === validationRequest) {
      validation.set(data.validation);
    }
  } finally {
    if (requestId === validationRequest) validating.set(false);
  }
}

export async function savePayload() {
  saving.set(true);
  try {
    const data = await requestJson<Record<string, any>>('/api/payload', {
      method: 'POST',
      body: JSON.stringify({ payload: get(payload) }),
    });
    if (data.validation) validation.set(data.validation);
    payloadState.set('Saved on device');
    showNotice(data.message || 'payload.dd saved.', data.notice || 'success');
  } catch (error: any) {
    if (error.data?.validation) validation.set(error.data.validation);
    showNotice(error.message, 'error');
  } finally {
    saving.set(false);
  }
}

export async function runPayload() {
  running.set(true);
  try {
    const data = await requestJson<Record<string, any>>('/api/run', {
      method: 'POST',
      body: JSON.stringify({ payload: get(payload), save: true }),
    });
    keyboardReady.set(true);
    payloadState.set('Saved on device');
    if (data.validation) validation.set(data.validation);
    runHistory.set(data.run_history || []);
    showNotice(data.message || 'Payload executed.', data.notice || 'success');
  } catch (error: any) {
    if (error.data?.validation) validation.set(error.data.validation);
    if (error.data?.run_history) runHistory.set(error.data.run_history);
    showNotice(error.message, 'error');
  } finally {
    running.set(false);
  }
}

export async function changeKeyboardTarget(next: {
  layout?: string;
  os?: string;
}) {
  try {
    const data = await requestJson<Record<string, any>>(
      '/api/keyboard-layout',
      {
        method: 'POST',
        body: JSON.stringify(next),
      },
    );
    applyKeyboardState(data);
    showNotice(
      data.message || 'Typing target updated.',
      data.notice || 'success',
    );
  } catch (error: any) {
    if (error.data) applyKeyboardState(error.data);
    showNotice(error.message, 'error');
  }
}

export async function loadLootSnapshot() {
  try {
    const data = await requestJson<LootRecord>('/api/loot');
    loot.set(data);
  } catch (error: any) {
    if (error.status === 404) loot.set(null);
  }
}

export async function importUsbLoot() {
  importingLoot.set(true);
  try {
    const data = await requestJson<Record<string, any>>(
      '/api/loot/import-usb',
      {
        method: 'POST',
        body: '{}',
      },
    );
    if (data.loot) loot.set(data.loot);
    showNotice(data.message || 'USB loot imported.', data.notice || 'success');
  } catch (error: any) {
    showNotice(error.message || 'USB loot import failed.', 'error');
  } finally {
    importingLoot.set(false);
  }
}

export async function uploadBinary(file: File) {
  uploadingBinary.set(true);
  uploadProgress.set(0);
  setArmoryNotice('Uploading...', 'quiet');
  try {
    const data = await uploadBinaryFile(file, (percent) =>
      uploadProgress.set(percent),
    );
    hasBinary.set(true);
    stagedBinaryName.set(data.filename || file.name);
    applyUsbAgent(data.usb_agent);
    setArmoryNotice(
      data.message || 'Upload complete.',
      data.notice || 'success',
    );
  } catch (error: any) {
    setArmoryNotice(error.message || 'Upload failed.', 'error');
  } finally {
    uploadingBinary.set(false);
  }
}

export async function injectBinary() {
  injectingBinary.set(true);
  setArmoryNotice('Injecting stager...', 'quiet');
  try {
    const data = await requestJson<Record<string, any>>('/api/inject_binary', {
      method: 'POST',
      body: JSON.stringify({ os: get(binaryTargetOs) }),
    });
    applyUsbAgent(data.usb_agent);
    if (data.run_history) runHistory.set(data.run_history);
    keyboardReady.set(true);
    setArmoryNotice(data.message || 'Injected.', data.notice || 'success');
  } catch (error: any) {
    applyUsbAgent(error.data?.usb_agent);
    if (error.data?.run_history) runHistory.set(error.data.run_history);
    setArmoryNotice(error.message || 'Injection failed.', 'error');
  } finally {
    injectingBinary.set(false);
  }
}

function applyLootUpdate(data: MessageEvent<string>) {
  try {
    loot.set(JSON.parse(data.data));
  } catch {
    // Ignore malformed stream frames; the snapshot path remains available.
  }
}

export function startLootStream() {
  if (lootStream || typeof EventSource === 'undefined') return () => {};
  lootStream = new EventSource('/api/loot/stream');
  lootStream.addEventListener('loot', applyLootUpdate as EventListener);
  lootStream.onerror = () => {
    loadLootSnapshot().catch(() => {});
  };
  return () => {
    lootStream?.close();
    lootStream = null;
  };
}

export async function startPortal() {
  await loadBootstrap();
  return startLootStream();
}
