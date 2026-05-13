/**
 * Application bootstrap: fetches device state on startup and wires up live streams.
 *
 * `loadBootstrap` fetches `/api/bootstrap` and fans the response out to every
 * domain store so they all reflect the current device state in one round-trip.
 *
 * `startPortal` calls `loadBootstrap`, then opens the loot SSE stream and
 * returns its teardown function.  Call it inside `onMount` and return the
 * teardown so Svelte cleans up on unmount.
 */
import { requestJson } from '../lib/api';
import type { BootstrapState } from '../lib/types';
import { apPassword, apSsid, authEnabled } from './ap';
import { hasBinary, stagedBinaryName } from './binary';
import { payload, payloadState, validation } from './editor';
import { applyKeyboardState, keyboardReady } from './keyboard';
import { loadLootSnapshot, startLootStream } from './loot';
import { runHistory, seededThisBoot } from './run';
import { showNotice } from './ui';
import { applyUsbAgent } from './usb';

function applyBootstrap(data: BootstrapState) {
  apSsid.set(data.ap_ssid || 'PicoBit');
  apPassword.set(data.ap_password || 'Open network');
  authEnabled.set(Boolean(data.auth_enabled));
  keyboardReady.set(Boolean(data.keyboard_ready));
  seededThisBoot.set(Boolean(data.seeded));
  hasBinary.set(Boolean(data.has_binary));
  runHistory.set(data.run_history || []);
  payload.set(data.payload || '');
  payloadState.set(data.seeded ? 'Seeded on boot' : 'Saved on device');
  if (data.validation) validation.set(data.validation);
  applyKeyboardState(data);
  applyUsbAgent(data.usb_agent);
  if (data.usb_agent?.filename) stagedBinaryName.set(data.usb_agent.filename);
  if (data.message) showNotice(data.message, data.notice || 'quiet');
}

/**
 * Fetch `/api/bootstrap` and distribute the response across all domain stores.
 * Also loads the initial loot snapshot so the loot viewer is populated before
 * the SSE stream takes over.
 */
export async function loadBootstrap() {
  const data = await requestJson<BootstrapState>('/api/bootstrap');
  applyBootstrap(data);
  await loadLootSnapshot();
}

/**
 * Bootstrap the portal and start the loot SSE stream.
 * Returns a cleanup function that closes the stream — pass it as the `onMount`
 * return value so it runs on component destroy.
 */
export async function startPortal(): Promise<() => void> {
  await loadBootstrap();
  return startLootStream();
}
