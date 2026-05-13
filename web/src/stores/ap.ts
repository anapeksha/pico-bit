/**
 * Wi-Fi access-point configuration surfaced from `/api/bootstrap`.
 * These values are display-only — they cannot be changed from the portal.
 */
import { writable } from 'svelte/store';

/** SSID broadcast by the Pico's built-in access point. */
export const apSsid = writable('PicoBit');

/** WPA2 password for the access point, or `'Open network'` when auth is disabled. */
export const apPassword = writable('Open network');

/** Whether HTTP basic-auth is enforced on the portal. */
export const authEnabled = writable(false);
