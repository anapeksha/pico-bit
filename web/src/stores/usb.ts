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
  active: false,
  root_url: 'http://192.168.7.1',
});

/** Human-readable NCM status derived from `ncmLink`. */
export const ncmLinkLabel = derived(ncmLink, ($ncm) => {
  return $ncm.active ? 'Active' : 'Inactive';
});

/** Overwrite `ncmLink` with a fresh snapshot; a no-op when `state` is undefined. */
export function applyNcmLink(state?: NcmLinkState) {
  if (state) ncmLink.set(state);
}
