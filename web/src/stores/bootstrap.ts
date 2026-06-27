/**
 * Application bootstrap: fetches device state on startup.
 *
 * `loadBootstrap` fetches `/api/bootstrap` and fans the response out to every
 * domain store so they all reflect the current device state in one round-trip.
 *
 * `startPortal` calls `loadBootstrap` and returns a no-op teardown for
 * symmetry with `onMount` conventions.
 */
import { get } from 'svelte/store';

import type {
  ArmoryFile,
  BootstrapState,
  HostHidState,
  KeyboardState,
  NcmLinkState,
  NoticeTone,
  RunHistoryItem,
} from '../api/contracts';
import { apPassword, apSsid } from './ap';
import {
  applyArmoryState,
  armoryFiles,
  armoryNotice,
  armoryUploadLimit,
  hasBinary,
  stagedBinaryName,
} from './binary';
import {
  configureBootstrapState,
  loadCachedBootstrap,
  refreshBootstrapSource,
} from './bootstrapCache';
import { payload, payloadState } from './editor';
import {
  applyHostHidState,
  applyKeyboardState,
  hostHid,
  keyboard,
  keyboardReady,
} from './keyboard';
import { runHistory, seededThisBoot } from './run';
import { showNotice } from './ui';
import { applyNcmLink, ncmLink } from './usb';

type BootstrapSnapshot = {
  apPassword: string;
  apSsid: string;
  armoryFiles: ArmoryFile[];
  armoryNotice: {
    message: string;
    tone: NoticeTone;
    visible: boolean;
  };
  armoryUploadLimit: number;
  hasBinary: boolean;
  hostHid: HostHidState;
  keyboard: KeyboardState;
  keyboardReady: boolean;
  ncmLink: NcmLinkState;
  payload: string;
  payloadState: string;
  runHistory: RunHistoryItem[];
  seededThisBoot: boolean;
  stagedBinaryName: string;
};

export function applyBootstrap(data: BootstrapState) {
  apSsid.set(data.ap_ssid || 'PicoBit');
  apPassword.set(data.ap_password || 'Open network');
  applyHostHidState(data.host_hid);
  seededThisBoot.set(Boolean(data.seeded));
  hasBinary.set(Boolean(data.has_binary));
  applyArmoryState(data);
  runHistory.set(data.run_history || []);
  payload.set(data.payload || '');
  payloadState.set(data.seeded ? 'Seeded on boot' : 'Saved on device');
  applyKeyboardState(data);
  applyNcmLink(data.ncm_link);
  if (data.ncm_link?.filename) stagedBinaryName.set(data.ncm_link.filename);
  if (data.message) showNotice(data.message, data.notice || 'quiet');
}

function captureBootstrapSnapshot(): BootstrapSnapshot {
  return {
    apPassword: get(apPassword),
    apSsid: get(apSsid),
    armoryFiles: get(armoryFiles),
    armoryNotice: get(armoryNotice),
    armoryUploadLimit: get(armoryUploadLimit),
    hasBinary: get(hasBinary),
    hostHid: get(hostHid),
    keyboard: get(keyboard),
    keyboardReady: get(keyboardReady),
    ncmLink: get(ncmLink),
    payload: get(payload),
    payloadState: get(payloadState),
    runHistory: get(runHistory),
    seededThisBoot: get(seededThisBoot),
    stagedBinaryName: get(stagedBinaryName),
  };
}

function restoreBootstrapSnapshot(snapshot: unknown) {
  const data = snapshot as BootstrapSnapshot;
  apPassword.set(data.apPassword);
  apSsid.set(data.apSsid);
  armoryFiles.set(data.armoryFiles);
  armoryNotice.set(data.armoryNotice);
  armoryUploadLimit.set(data.armoryUploadLimit);
  hasBinary.set(data.hasBinary);
  hostHid.set(data.hostHid);
  keyboard.set(data.keyboard);
  keyboardReady.set(data.keyboardReady);
  ncmLink.set(data.ncmLink);
  payload.set(data.payload);
  payloadState.set(data.payloadState);
  runHistory.set(data.runHistory);
  seededThisBoot.set(data.seededThisBoot);
  stagedBinaryName.set(data.stagedBinaryName);
}

configureBootstrapState({
  apply: applyBootstrap,
  capture: captureBootstrapSnapshot,
  restore: restoreBootstrapSnapshot,
});

/**
 * Fetch `/api/bootstrap` and distribute the response across all domain stores.
 * This is the only startup fetch; mutations reconcile through the same cache.
 */
export async function loadBootstrap() {
  await loadCachedBootstrap();
}

export async function refreshBootstrap() {
  await refreshBootstrapSource();
}

/**
 * Bootstrap the portal and start the loot SSE stream.
 * Returns a cleanup function that closes the stream — pass it as the `onMount`
 * return value so it runs on component destroy.
 */
export async function startPortal(): Promise<() => void> {
  await loadBootstrap();
  return () => {};
}
