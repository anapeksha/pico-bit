import { writable } from 'svelte/store';

/** Machine-readable action names rendered by the Activity panel. */
export type ActivityCode =
  | 'armory_delete_complete'
  | 'armory_delete_failed'
  | 'armory_upload_complete'
  | 'armory_upload_failed'
  | 'keyboard_target_changed'
  | 'keyboard_target_failed'
  | 'payload_run_failed'
  | 'payload_run_requested'
  | 'payload_save_failed'
  | 'payload_saved';

/** One resolved dashboard action in the current browser session. */
export type ActivityItem = {
  code: ActivityCode;
  ok: boolean;
  sequence: number;
};

const ACTIVITY_LIMIT = 6;
let nextSequence = 1;

/** Recent explicit dashboard actions, newest first. */
export const activity = writable<ActivityItem[]>([]);

/** Records one resolved dashboard action in the bounded session timeline. */
export function recordActivity(code: ActivityCode, ok: boolean) {
  const item = { code, ok, sequence: nextSequence };
  nextSequence += 1;
  activity.update((items) => [item, ...items].slice(0, ACTIVITY_LIMIT));
}
