/**
 * Binary Armory state: upload and staging for files stored on the device.
 *
 * Upload is performed via XHR (not `fetch`) to expose upload progress.
 * `armoryNotice` is a section-local notice distinct from the global toast;
 * use `setArmoryNotice` rather than writing to the store directly.
 */
import { derived, writable } from 'svelte/store';

import { deleteBinaryFile, uploadBinaryFile } from '../api/client';
import type { ArmoryFile, BootstrapState, NoticeTone, TargetOs } from '../api/contracts';
import { MAX_ARMORY_FILE_SIZE } from '../lib/binary';
import { refreshBootstrapSource, withOptimisticBootstrap } from './bootstrapCache';
import { keyboard } from './keyboard';
import { applyNcmLink } from './usb';

const OS_CODE_TO_TARGET: Record<string, TargetOs> = {
  MAC: 'macos',
  LINUX: 'linux',
  WIN: 'windows',
};

/** `true` when a staged binary is present on the device. */
export const hasBinary = writable(false);

/** Filename of the currently staged binary, empty string when none. */
export const stagedBinaryName = writable('');

/** Files currently reported by the device armory or bootstrap snapshot. */
export const armoryFiles = writable<ArmoryFile[]>([]);

/** XHR upload progress 0–100. */
export const uploadProgress = writable(0);

/** Maximum single-file upload size accepted by the firmware. */
export const armoryUploadLimit = writable(MAX_ARMORY_FILE_SIZE);

/** `true` while a binary upload is in progress. */
export const uploadingBinary = writable(false);

/** Target OS for the HID stager script, derived from the active keyboard OS selection. */
export const binaryTargetOs = derived(keyboard, ($k) => OS_CODE_TO_TARGET[$k.os] ?? 'windows');

/** Section-local status notice shown inside Binary Armory. */
export const armoryNotice = writable<{
  message: string;
  tone: NoticeTone;
  visible: boolean;
}>({
  message: '',
  tone: 'quiet',
  visible: false,
});

/** Show or clear the Binary Armory section notice. Pass an empty string to hide. */
export function setArmoryNotice(message: string, tone: NoticeTone = 'quiet') {
  armoryNotice.set({ message, tone, visible: Boolean(message) });
}

export function applyArmoryState(
  data: Pick<BootstrapState, 'files' | 'has_binary' | 'ncm_link' | 'max_upload_bytes'>,
) {
  const files = data.files || [];
  if (data.max_upload_bytes) armoryUploadLimit.set(data.max_upload_bytes);
  armoryFiles.set(
    files.map((file) => ({
      name: file.name,
      kind: file.kind,
      path: file.path,
      size: file.size,
      url: file.path || file.name,
    })),
  );
  hasBinary.set(Boolean(data.has_binary));
  if (data.ncm_link?.filename) stagedBinaryName.set(data.ncm_link.filename);
  applyNcmLink(data.ncm_link);
}

export async function refreshArmory() {
  await refreshBootstrapSource();
}

/**
 * Upload a binary file to the device via XHR, reporting progress through
 * `uploadProgress`.  On success `hasBinary` and `stagedBinaryName` are updated.
 */
export async function uploadBinary(file: File) {
  uploadingBinary.set(true);
  uploadProgress.set(0);
  try {
    const data = await withOptimisticBootstrap(
      () => {
        setArmoryNotice('Uploading...', 'quiet');
        hasBinary.set(true);
        stagedBinaryName.set(file.name);
        armoryFiles.update((files) => [
          ...files.filter((item) => item.name !== file.name),
          {
            kind: 'asset',
            name: file.name,
            path: `/armory/${file.name}`,
            size: file.size,
            url: `/armory/${file.name}`,
          },
        ]);
      },
      () => uploadBinaryFile(file, (percent) => uploadProgress.set(percent)),
    );
    setArmoryNotice(data.message || 'Upload complete.', data.notice || 'success');
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Upload failed.';
    setArmoryNotice(message, 'error');
  } finally {
    uploadingBinary.set(false);
  }
}

export async function deleteBinary(filename: string) {
  try {
    const data = await withOptimisticBootstrap(
      () => {
        setArmoryNotice('Deleting...', 'quiet');
        armoryFiles.update((files) => files.filter((file) => file.name !== filename));
      },
      () => deleteBinaryFile(filename),
    );
    setArmoryNotice(data.message || 'File removed from flash.', data.notice || 'success');
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Delete failed.';
    setArmoryNotice(message, 'error');
  }
}
