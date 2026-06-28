import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { runPayload as runPayloadApi, savePayload as savePayloadApi } from '../api/client';
import { refreshBootstrapSource } from './bootstrapCache';
import {
  payload,
  payloadState,
  runPayload,
  running,
  savePayload,
  saving,
  validation,
} from './editor';

vi.mock('../api/client', () => ({
  runPayload: vi.fn(),
  savePayload: vi.fn(),
}));

vi.mock('./bootstrapCache', () => ({
  refreshBootstrapSource: vi.fn(),
}));

vi.mock('./ui', async () => {
  const { writable } = await import('svelte/store');
  return {
    showNotice: vi.fn(),
    validationModalOpen: writable(false),
  };
});

describe('editor store savePayload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    payload.set('STRING Ready');
    payloadState.set('Unsaved changes');
    saving.set(false);
    running.set(false);
    validation.set(null);
    vi.mocked(savePayloadApi).mockResolvedValue({
      error_line: null,
      message: 'Payload updated successfully.',
      success: true,
    });
    vi.mocked(runPayloadApi).mockResolvedValue({
      error_line: null,
      message: 'Payload injection sequence initialized.',
      success: true,
    });
    vi.mocked(refreshBootstrapSource).mockResolvedValue({} as never);
  });

  it('saves the editor text to payload.dd without triggering run', async () => {
    await savePayload();

    expect(savePayloadApi).toHaveBeenCalledWith({ code: 'STRING Ready' });
    expect(runPayloadApi).not.toHaveBeenCalled();
    expect(refreshBootstrapSource).toHaveBeenCalledTimes(1);
    expect(get(payloadState)).toBe('Saved on device');
    expect(get(validation)).toBeNull();
  });

  it('runs the saved payload without saving the editor draft', async () => {
    await runPayload();

    expect(runPayloadApi).toHaveBeenCalledTimes(1);
    expect(savePayloadApi).not.toHaveBeenCalled();
    expect(refreshBootstrapSource).toHaveBeenCalledTimes(1);
    expect(get(validation)).toBeNull();
  });
});
