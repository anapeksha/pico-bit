/**
 * Host USB agent state as reported by the device.
 *
 * `hostUsb` mirrors the raw `UsbAgentState` object from the server.
 * `usbStateLabel` derives a single human-readable summary string for display.
 * `applyUsbAgent` is called by bootstrap and binary-injection responses
 * whenever the server returns an updated agent snapshot.
 */
import { derived, writable } from 'svelte/store';

import type { UsbAgentState } from '../lib/types';

/** Raw USB agent state from the device. */
export const hostUsb = writable<UsbAgentState>({
  available: false,
  message: 'Waiting',
  mounted: false,
  state: 'inactive',
});

/** Human-readable USB agent status derived from `hostUsb`. */
export const usbStateLabel = derived(hostUsb, ($usb) => {
  if (!$usb.available) return 'Unavailable';
  if ($usb.mounted || $usb.active || $usb.state === 'active') return 'Active';
  if ($usb.state === 'error') return 'Error';
  return 'Inactive';
});

/** Overwrite `hostUsb` with a fresh snapshot; a no-op when `state` is undefined. */
export function applyUsbAgent(state?: UsbAgentState) {
  if (state) hostUsb.set(state);
}
