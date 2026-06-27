import { describe, expect, it, vi } from 'vitest';

import { createResourceCache } from './cache';

describe('createResourceCache', () => {
  it('returns cached data after the first fetch', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce({ value: 1 });
    const cache = createResourceCache(fetcher);

    await expect(cache.get()).resolves.toEqual({ value: 1 });
    await expect(cache.get()).resolves.toEqual({ value: 1 });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('deduplicates concurrent reads', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce({ value: 1 });
    const cache = createResourceCache(fetcher);

    const [first, second] = await Promise.all([cache.get(), cache.get()]);

    expect(first).toEqual({ value: 1 });
    expect(second).toEqual({ value: 1 });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('force-refreshes when requested', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce({ value: 1 }).mockResolvedValueOnce({ value: 2 });
    const cache = createResourceCache(fetcher);

    await expect(cache.get()).resolves.toEqual({ value: 1 });
    await expect(cache.refresh()).resolves.toEqual({ value: 2 });
    await expect(cache.get()).resolves.toEqual({ value: 2 });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
