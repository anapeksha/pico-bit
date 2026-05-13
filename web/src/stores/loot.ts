/**
 * Agent loot state: snapshot loading, USB drive import, and live SSE stream.
 *
 * On startup, `loadLootSnapshot` fetches any existing loot from the device.
 * `startLootStream` then opens a persistent SSE connection that pushes
 * incremental updates as the agent writes data back to the Pico drive.
 * On SSE error the stream closes and falls back to a one-shot snapshot fetch.
 *
 * `importUsbLoot` triggers a manual read of the USB drive loot file — useful
 * when the drive already contained data before this portal session started.
 */
import { writable } from 'svelte/store';

import { requestJson } from '../lib/api';
import type { LootRecord } from '../lib/types';
import { showNotice } from './ui';

/** Current loot record, or `null` when no loot has been collected yet. */
export const loot = writable<LootRecord | null>(null);

/** `true` while a USB loot import request is in flight. */
export const importingLoot = writable(false);

let lootStream: EventSource | null = null;

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

function applyLootUpdate(data: MessageEvent<string>) {
  try {
    loot.set(JSON.parse(data.data));
  } catch {
    // Ignore malformed stream frames; the snapshot path remains available.
  }
}

/**
 * Open an SSE connection to `/api/loot/stream` and update `loot` on each
 * `loot` event.  On error the stream closes and falls back to a snapshot fetch.
 * Returns a teardown function — call it on component destroy or portal stop.
 */
export function startLootStream(): () => void {
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
