/**
 * Shared UI state that does not belong to any single domain:
 * top-bar notice toasts, the validation error modal, and the active
 * accordion panel in the middle column.
 */
import { writable } from 'svelte/store';

import type { NoticeTone } from '../lib/types';

let noticeTimer = 0;

/** Active toast notification shown in the top-right corner. */
export const notice = writable<{ message: string; tone: NoticeTone; visible: boolean }>({
  message: '',
  tone: 'quiet',
  visible: false,
});

/** Whether the validation-error detail modal is open. */
export const validationModalOpen = writable(false);

/** Which editor accordion is currently expanded — `'ducky'` or `'armory'`. */
export const activeAccordion = writable<'ducky' | 'armory'>('ducky');

/**
 * Display a top-bar notice toast and auto-dismiss it after 2 seconds.
 * Calling with an empty `message` hides the toast immediately.
 */
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
