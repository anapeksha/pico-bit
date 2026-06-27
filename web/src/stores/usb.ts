/**
 * NCM link state as reported by the device.
 *
 * `ncmLink` mirrors the raw `NcmLinkState` object from the server.
 * `ncmLinkLabel` derives a single human-readable summary string for display.
 * `applyNcmLink` is called by bootstrap or another integration layer whenever
 * the server returns an updated transport snapshot.
 */
import { derived, writable } from 'svelte/store';

import type { NcmLinkState } from '../api/contracts';

/** Raw NCM link state from the device. */
export const ncmLink = writable<NcmLinkState>({
  available: false,
  message: 'Waiting',
  state: 'inactive',
  transport: 'ncm',
});

/** Human-readable NCM status derived from `ncmLink`. */
export const ncmLinkLabel = derived(ncmLink, ($ncm) => {
  if (!$ncm.available) return 'Unavailable';
  if ($ncm.active || $ncm.state === 'active') return 'Active';
  if ($ncm.state === 'error') return 'Error';
  return 'Inactive';
});

/** Overwrite `ncmLink` with a fresh snapshot; a no-op when `state` is undefined. */
export function applyNcmLink(state?: NcmLinkState) {
  if (state) ncmLink.set(state);
}
