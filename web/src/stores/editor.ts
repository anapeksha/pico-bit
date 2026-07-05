/**
 * DuckyScript editor state: payload text and save actions.
 *
 * Validation is performed by the firmware as part of save and run requests.
 *
 * `canSave` is a derived read-only store — do not write to it.
 */
import { derived, get, writable } from 'svelte/store';

import { runPayload as runPayloadApi, savePayload as savePayloadApi } from '../api/client';
import type {
  PayloadMutationResponse,
  PayloadRunResponse,
  RequestFailure,
  ValidationState,
} from '../api/contracts';
import { refreshBootstrapSource } from './bootstrapCache';
import { showNotice, validationModalOpen } from './ui';

/** The current payload text bound to the editor textarea. */
export const payload = writable('');

/** Human-readable save/edit status shown in the editor badge. */
export const payloadState = writable('Saved on device');

/** Most recent validation result from the device, or `null` before the first check. */
export const validation = writable<ValidationState | null>(null);

/** `true` while a save request is in flight. */
export const saving = writable(false);

/** `true` while a run request is in flight. */
export const running = writable(false);

/** `true` when a save request can be submitted. Save performs validation server-side. */
export const canSave = derived([saving, running], ([$saving, $running]) => !$saving && !$running);

/** `true` when the persisted payload can be run. Run performs validation server-side. */
export const canRun = derived([saving, running], ([$saving, $running]) => !$saving && !$running);

function validationFromFirmware(
  data: PayloadMutationResponse | PayloadRunResponse,
): ValidationState {
  if (data.validation) return data.validation;

  const message = data.message || (data.success ? 'Script is valid.' : 'Syntax validation failed.');
  return {
    badge_label: data.success ? 'Ready' : 'Errors',
    badge_tone: data.success ? 'success' : 'error',
    blocking: !data.success,
    can_run: data.success,
    can_save: data.success,
    diagnostics:
      !data.success && data.error_line
        ? [
            {
              column: 1,
              line: data.error_line,
              message,
              severity: 'error',
            },
          ]
        : [],
    error_count: data.success ? 0 : 1,
    line_count: get(payload).split('\n').length,
    notice: data.success ? 'success' : 'error',
    summary: message,
    warning_count: 0,
  };
}

function applyValidationFailure(data: PayloadMutationResponse | PayloadRunResponse) {
  validation.set(validationFromFirmware(data));
  validationModalOpen.set(true);
}

/** Save the current payload to payload.dd after firmware validation passes. */
export async function savePayload() {
  saving.set(true);
  try {
    const draft = get(payload);
    const data = await savePayloadApi({ code: draft });
    const nextValidation = validationFromFirmware(data);
    validation.set(nextValidation);

    if (!data.success) {
      applyValidationFailure(data);
      showNotice(data.message || 'Syntax validation failed.', 'error');
      return;
    }

    validation.set(null);
    payloadState.set('Saved on device');
    await refreshBootstrapSource();
    showNotice(data.message || 'Payload saved to payload.dd.', 'success');
  } catch (error: unknown) {
    const failure = error as RequestFailure;
    if (failure.data) {
      applyValidationFailure(failure.data as PayloadMutationResponse);
    }
    showNotice(error instanceof Error ? error.message : 'Save failed.', 'error');
  } finally {
    saving.set(false);
  }
}

/** Save the current editor draft, then run payload.dd after firmware validation passes. */
export async function runPayload() {
  running.set(true);
  try {
    const draft = get(payload);
    const saved = await savePayloadApi({ code: draft });

    if (!saved.success) {
      applyValidationFailure(saved);
      showNotice(saved.message || 'Syntax validation failed.', 'error');
      return;
    }

    const data = await runPayloadApi();

    if (!data.success) {
      applyValidationFailure(data);
      showNotice(data.message || 'Syntax validation failed.', 'error');
      return;
    }

    validation.set(null);
    payloadState.set('Saved on device');
    await refreshBootstrapSource();
    showNotice(data.message || 'Payload run started.', 'success');
  } catch (error: unknown) {
    const failure = error as RequestFailure;
    if (failure.data) {
      applyValidationFailure(failure.data as PayloadRunResponse);
    }
    showNotice(error instanceof Error ? error.message : 'Run failed.', 'error');
  } finally {
    running.set(false);
  }
}
