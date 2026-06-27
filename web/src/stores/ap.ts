/**
 * Wi-Fi access-point configuration surfaced from `/api/bootstrap`.
 * These values are display-only — they cannot be changed from the portal.
 */
import { writable } from 'svelte/store';

/** SSID broadcast by the Pico's built-in access point. */
export const apSsid = writable('PicoBit');

/** WPA2 password for the access point, or `'Open network'` when the AP is open. */
export const apPassword = writable('Open network');
