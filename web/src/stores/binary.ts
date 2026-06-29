/**
 * Binary Armory state: upload and staging for files stored on the device.
 *
 * Upload is performed via XHR (not `fetch`) to expose upload progress.
 * `armoryNotice` is a section-local notice distinct from the global toast;
 * use `setArmoryNotice` rather than writing to the store directly.
 */
import { writable } from 'svelte/store';

import { deleteBinaryFile, uploadBinaryFile } from '../api/client';
import type { ArmoryFile, HydratedBootstrapState, NoticeTone } from '../api/contracts';
import { withOptimisticBootstrap } from './bootstrapCache';

/** Files currently reported by the device armory snapshot. */
export const armoryFiles = writable<ArmoryFile[]>([]);

/** XHR upload progress 0–100. */
export const uploadProgress = writable(0);

/** `true` while a binary upload is in progress. */
export const uploadingBinary = writable(false);

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

export function applyArmoryState(data: Pick<HydratedBootstrapState, 'files'>) {
  const files = data.files || [];
  armoryFiles.set(
    files.map((file) => ({
      name: file.name,
      kind: file.kind,
      path: file.path,
      size: file.size,
      url: file.path || file.name,
    })),
  );
}

/**
 * Upload a binary file to the device via XHR, reporting progress through `uploadProgress`.
 */
export async function uploadBinary(file: File) {
  uploadingBinary.set(true);
  uploadProgress.set(0);
  try {
    const data = await withOptimisticBootstrap(
      () => {
        setArmoryNotice('Uploading...', 'quiet');
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
