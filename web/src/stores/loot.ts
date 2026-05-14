/**
 * Agent loot state: snapshot loading and USB drive import.
 *
 * `loadLootSnapshot` fetches any existing loot from the device on startup and
 * whenever the execution stream signals completion.
 * `importUsbLoot` triggers a manual read of the USB drive loot file.
 */
import { writable } from 'svelte/store';

import { requestJson } from '../lib/api';
import type { LootRecord } from '../lib/types';
import { showNotice } from './ui';

/** Current loot record, or `null` when no loot has been collected yet. */
export const loot = writable<LootRecord | null>(null);

/** `true` while a USB loot import request is in flight. */
export const importingLoot = writable(false);

/**
 * Fetch the current loot snapshot from `/api/loot`.
 * Sets `loot` to `null` on a 404 (no loot collected yet).
 */
export async function loadLootSnapshot() {
  try {
    const data = await requestJson<LootRecord>('/api/loot');
    loot.set(data);
  } catch (error: any) {
    if (error.status === 404) loot.set(null);
  }
}

/**
 * POST to `/api/loot/import-usb` to read loot written by the agent to the
 * Pico USB drive.  Updates `loot` with the returned record on success.
 */
export async function importUsbLoot() {
  importingLoot.set(true);
  try {
    const data = await requestJson<Record<string, any>>('/api/loot/import-usb', {
      method: 'POST',
      body: '{}',
    });
    if (data.loot) loot.set(data.loot);
    showNotice(data.message || 'USB loot imported.', data.notice || 'success');
  } catch (error: any) {
    showNotice(error.message || 'USB loot import failed.', 'error');
  } finally {
    importingLoot.set(false);
  }
}
