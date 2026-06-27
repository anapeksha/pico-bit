/**
 * DuckyScript editor state: payload text, explicit validation, and save actions.
 *
 * Validation is intentionally async and cancellable. It is only invoked by
 * explicit actions such as save or a manual validation control, not on typing.
 *
 * `canSave` is a derived read-only store — do not write to it.
 */
import { derived, get, writable } from 'svelte/store';

import { savePayload as savePayloadApi, validatePayload } from '../api/client';
import type { PayloadMutationResponse, RequestFailure, ValidationState } from '../api/contracts';
import { withOptimisticBootstrap } from './bootstrapCache';
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

/** `true` when a save request can be submitted. Save performs validation server-side. */
export const canSave = derived(saving, ($saving) => !$saving);

function validationFromFirmware(data: PayloadMutationResponse): ValidationState {
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

/**
 * POST the given script (defaults to the current `payload`) to `/api/payload/validate`
 * and update `validation`.  Stale responses from superseded requests are
 * silently dropped.
 */
export async function validatePayloadDraft(script = get(payload)) {
  const requestId = ++validationRequest;
  validating.set(true);
  try {
    const data = await validatePayload({ code: script });
    if (requestId === validationRequest) {
      validation.set(validationFromFirmware(data));
    }
  } finally {
    if (requestId === validationRequest) validating.set(false);
  }
}

/** Save the current payload to the device and update `validation` from the response. */
export async function savePayload() {
  saving.set(true);
  try {
    const draft = get(payload);
    const data = await withOptimisticBootstrap(
      () => {
        payloadState.set('Saved on device');
      },
      () => savePayloadApi({ code: draft }),
    );
    showNotice(
      data.message || 'payload.dd saved.',
      data.success ? data.notice || 'success' : 'error',
    );
  } catch (error: unknown) {
    const failure = error as RequestFailure;
    if (failure.data?.validation) validation.set(failure.data.validation as ValidationState);
    showNotice(error instanceof Error ? error.message : 'Save failed.', 'error');
  } finally {
    saving.set(false);
  }
}
