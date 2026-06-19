/**
 * DuckyScript editor state: payload text, live validation, and save/run actions.
 *
 * Validation is intentionally async and cancellable — concurrent requests are
 * tracked by a monotonic `validationRequest` counter so only the response to
 * the most recent request is applied.  The component is responsible for
 * debouncing calls to `validatePayloadDraft`.
 *
 * `canSave` and `canRun` are derived read-only stores — do not write to them.
 */
import { derived, get, writable } from 'svelte/store';

import { requestJson } from '../lib/api';
import type { ValidationState } from '../lib/types';
import { runHistory } from './run';
import { showNotice } from './ui';

let validationRequest = 0;

/** The current payload text bound to the editor textarea. */
export const payload = writable('');

/** Human-readable save/edit status shown in the editor badge. */
export const payloadState = writable('Saved on device');

/** Most recent validation result from the device, or `null` before the first check. */
export const validation = writable<ValidationState | null>(null);

/** `true` while a validation request is in flight. */
export const validating = writable(false);

/** `true` while a save request is in flight. */
export const saving = writable(false);

/** `true` while a run request is in flight. */
export const running = writable(false);

/** `true` when the payload can be saved (valid, not currently saving or validating). */
export const canSave = derived(
  [validation, validating, saving],
  ([$validation, $validating, $saving]) =>
    !$validating && !$saving && Boolean($validation?.can_save),
);

/** `true` when the payload can be executed (valid, not currently running or validating). */
export const canRun = derived(
  [validation, validating, running],
  ([$validation, $validating, $running]) =>
    !$validating && !$running && Boolean($validation?.can_run),
);

/**
 * POST the given script (defaults to the current `payload`) to `/api/validate`
 * and update `validation`.  Stale responses from superseded requests are
 * silently dropped.
 */
export async function validatePayloadDraft(script = get(payload)) {
  const requestId = ++validationRequest;
  validating.set(true);
  try {
    const data = await requestJson<{ validation: ValidationState }>('/api/validate', {
      method: 'POST',
      body: JSON.stringify({ payload: script }),
    });
    if (requestId === validationRequest) {
      validation.set(data.validation);
    }
  } finally {
    if (requestId === validationRequest) validating.set(false);
  }
}

/** Save the current payload to the device and update `validation` from the response. */
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

/** Save and immediately execute the current payload on the device. */
export async function runPayload() {
  running.set(true);
  try {
    const data = await requestJson<Record<string, any>>('/api/run', {
      method: 'POST',
      body: JSON.stringify({ payload: get(payload), save: true }),
    });
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
