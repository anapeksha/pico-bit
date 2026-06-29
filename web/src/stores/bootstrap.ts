/**
 * Application bootstrap: fetches device state on startup.
 *
 * `loadBootstrap` fetches `/api/bootstrap` and fans the response out to every
 * domain store so they all reflect the current device state in one round-trip.
 *
 * `startApp` calls `loadBootstrap` and returns the dashboard teardown hook.
 */
import { get } from 'svelte/store';

import type {
  ArmoryFile,
  HydratedBootstrapState,
  KeyboardState,
  NoticeTone,
  RunHistoryItem,
} from '../api/contracts';
import { apPassword, apSsid } from './ap';
import { applyArmoryState, armoryFiles, armoryNotice } from './binary';
import { configureBootstrapState, loadCachedBootstrap } from './bootstrapCache';
import { payload, payloadState } from './editor';
import {
  applyHostHidState,
  applyKeyboardState,
  hostHid,
  keyboard,
  keyboardReady,
} from './keyboard';
import { runHistory, seededThisBoot } from './run';
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
  hostHid: {
    active?: boolean;
  };
  keyboard: KeyboardState;
  keyboardReady: boolean;
  ncmLink: {
    active?: boolean;
    root_url?: string;
  };
  payload: string;
  payloadState: string;
  runHistory: RunHistoryItem[];
  seededThisBoot: boolean;
};

export function applyBootstrap(data: HydratedBootstrapState) {
  apSsid.set(data.ap_ssid || 'PicoBit');
  apPassword.set(data.ap_password || 'Open network');
  applyHostHidState({ active: Boolean(data.host_hid_active) });
  seededThisBoot.set(Boolean(data.seeded));
  applyArmoryState(data);
  runHistory.set(data.run_history || []);
  payload.set(data.payload || '');
  payloadState.set(data.seeded ? 'Seeded on boot' : 'Saved on device');
  applyKeyboardState(data);
  applyNcmLink({ active: Boolean(data.ncm_active), root_url: data.ncm_url });
}

function captureBootstrapSnapshot(): BootstrapSnapshot {
  return {
    apPassword: get(apPassword),
    apSsid: get(apSsid),
    armoryFiles: get(armoryFiles),
    armoryNotice: get(armoryNotice),
    hostHid: get(hostHid),
    keyboard: get(keyboard),
    keyboardReady: get(keyboardReady),
    ncmLink: get(ncmLink),
    payload: get(payload),
    payloadState: get(payloadState),
    runHistory: get(runHistory),
    seededThisBoot: get(seededThisBoot),
  };
}

function restoreBootstrapSnapshot(snapshot: unknown) {
  const data = snapshot as BootstrapSnapshot;
  apPassword.set(data.apPassword);
  apSsid.set(data.apSsid);
  armoryFiles.set(data.armoryFiles);
  armoryNotice.set(data.armoryNotice);
  hostHid.set(data.hostHid);
  keyboard.set(data.keyboard);
  keyboardReady.set(data.keyboardReady);
  ncmLink.set(data.ncmLink);
  payload.set(data.payload);
  payloadState.set(data.payloadState);
  runHistory.set(data.runHistory);
  seededThisBoot.set(data.seededThisBoot);
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

/**
 * Bootstrap the dashboard. Returns a teardown function for `onMount`.
 */
export async function startApp(): Promise<() => void> {
  await loadBootstrap();
  return () => {};
}
