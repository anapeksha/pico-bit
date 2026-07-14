import { get } from 'svelte/store';
import { beforeEach, describe, expect, it } from 'vitest';

import { activity, recordActivity } from './activity';

describe('activity timeline', () => {
  beforeEach(() => activity.set([]));

  it('keeps the six newest resolved actions', () => {
    for (let index = 0; index < 8; index += 1) {
      recordActivity(index % 2 === 0 ? 'payload_saved' : 'payload_save_failed', index % 2 === 0);
    }

    const items = get(activity);
    expect(items).toHaveLength(6);
    expect(items[0].sequence).toBeGreaterThan(items[5].sequence);
  });
});
