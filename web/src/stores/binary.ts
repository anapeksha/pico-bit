/**
 * Binary Armory state: upload, staging, and HID-injection of agent binaries.
 *
 * Upload is performed via XHR (not `fetch`) to expose upload progress.
 * `injectBinary` opens the execution SSE stream before the POST so the
 * timeline component starts reacting immediately when the server begins
 * emitting step events.
 *
 * `armoryNotice` is a section-local notice distinct from the global toast;
 * use `setArmoryNotice` rather than writing to the store directly.
 */
import { derived, get, writable } from 'svelte/store';

import { requestJson, uploadBinaryFile } from '../lib/api';
import type { NoticeTone, TargetOs } from '../lib/types';
import { startExecutionStream } from './execution';
import { keyboard } from './keyboard';
import { runHistory } from './run';
import { applyUsbAgent } from './usb';

const OS_CODE_TO_TARGET: Record<string, TargetOs> = {
  MAC: 'macos',
  LINUX: 'linux',
  WIN: 'windows',
};

/** `true` when a staged binary is present on the device. */
export const hasBinary = writable(false);

/** Filename of the currently staged binary, empty string when none. */
export const stagedBinaryName = writable('');

/** XHR upload progress 0–100. */
export const uploadProgress = writable(0);

/** `true` while a binary upload is in progress. */
export const uploadingBinary = writable(false);

/** `true` while the HID injection POST is in flight. */
export const injectingBinary = writable(false);

/** Target OS for the HID stager script, derived from the active keyboard OS selection. */
export const binaryTargetOs = derived(keyboard, ($k) => OS_CODE_TO_TARGET[$k.os] ?? 'windows');

/** Section-local status notice shown inside Binary Armory. */
export const armoryNotice = writable<{ message: string; tone: NoticeTone; visible: boolean }>({
  message: '',
  tone: 'quiet',
  visible: false,
});

/** Show or clear the Binary Armory section notice. Pass an empty string to hide. */
export function setArmoryNotice(message: string, tone: NoticeTone = 'quiet') {
  armoryNotice.set({ message, tone, visible: Boolean(message) });
}

/**
 * Upload a binary file to the device via XHR, reporting progress through
 * `uploadProgress`.  On success `hasBinary` and `stagedBinaryName` are updated.
 */
export async function uploadBinary(file: File) {
  uploadingBinary.set(true);
  uploadProgress.set(0);
  setArmoryNotice('Uploading...', 'quiet');
  try {
    const data = await uploadBinaryFile(file, (percent) => uploadProgress.set(percent));
    hasBinary.set(true);
    stagedBinaryName.set(data.filename || file.name);
    applyUsbAgent(data.usb_agent);
    setArmoryNotice(data.message || 'Upload complete.', data.notice || 'success');
  } catch (error: any) {
    setArmoryNotice(error.message || 'Upload failed.', 'error');
  } finally {
    uploadingBinary.set(false);
  }
}

/**
 * Start the execution SSE stream and POST to `/api/inject_binary` to trigger
 * the HID stager on the device.  The stream receives step events while the
 * POST is blocking (HID typing takes several seconds), so both run concurrently
 * via the browser's parallel connection pool.
 */
export async function injectBinary() {
  injectingBinary.set(true);
  setArmoryNotice('Injecting stager...', 'quiet');
  const stopStream = startExecutionStream();
  try {
    const data = await requestJson<Record<string, any>>('/api/inject_binary', {
      method: 'POST',
      body: JSON.stringify({ os: get(binaryTargetOs) }),
    });
    applyUsbAgent(data.usb_agent);
    if (data.run_history) runHistory.set(data.run_history);
    setArmoryNotice(data.message || 'Injected.', data.notice || 'success');
  } catch (error: any) {
    applyUsbAgent(error.data?.usb_agent);
    if (error.data?.run_history) runHistory.set(error.data.run_history);
    setArmoryNotice(error.message || 'Injection failed.', 'error');
  } finally {
    injectingBinary.set(false);
    stopStream();
  }
}
