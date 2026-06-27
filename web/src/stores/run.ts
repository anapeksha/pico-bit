/**
 * Payload run history and boot-seeding state.
 *
 * `runHistory` is populated on bootstrap when the firmware includes history.
 * `seededThisBoot` is `true` when the device executed a seed payload on
 * startup rather than waiting for a manual trigger.
 */
import { writable } from 'svelte/store';

import type { RunHistoryItem } from '../api/contracts';

/** Ordered list of past payload executions, newest first. */
export const runHistory = writable<RunHistoryItem[]>([]);

/** `true` when the device ran a payload automatically on this boot. */
export const seededThisBoot = writable(false);
