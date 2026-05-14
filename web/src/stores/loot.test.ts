import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('loot store', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function freshImport() {
    const mod = await import('./loot');
    return mod;
  }

  it('loadLootSnapshot sets loot on success', async () => {
    const record = { source: 'usb_drive', type: 'recon' };
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(record),
    } as unknown as Response);

    const { loot, loadLootSnapshot } = await freshImport();
    await loadLootSnapshot();
    expect(get(loot)).toEqual(record);
  });

  it('loadLootSnapshot sets null on 404', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: vi.fn().mockResolvedValue({ message: 'not found' }),
    } as unknown as Response);

    const { loot, loadLootSnapshot } = await freshImport();
    loot.set({ type: 'recon' }); // pre-populate
    await loadLootSnapshot();
    expect(get(loot)).toBeNull();
  });

  it('loadLootSnapshot leaves loot unchanged on non-404 error', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue({ message: 'server error' }),
    } as unknown as Response);

    const { loot, loadLootSnapshot } = await freshImport();
    const initial = { type: 'recon' };
    loot.set(initial);
    await loadLootSnapshot();
    expect(get(loot)).toEqual(initial);
  });

  it('importUsbLoot updates loot and shows success notice on 200', async () => {
    const imported = { source: 'usb_drive', type: 'recon' };
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ loot: imported, message: 'Imported.', notice: 'success' }),
    } as unknown as Response);

    const { loot, importingLoot, importUsbLoot } = await freshImport();
    await importUsbLoot();
    expect(get(loot)).toEqual(imported);
    expect(get(importingLoot)).toBe(false);
  });

  it('importUsbLoot clears importingLoot flag on error', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue({ message: 'drive error' }),
    } as unknown as Response);

    const { importingLoot, importUsbLoot } = await freshImport();
    await importUsbLoot();
    expect(get(importingLoot)).toBe(false);
  });

  it('startLootStream returns a teardown function', async () => {
    const closeSpy = vi.fn();
    const addEventListenerSpy = vi.fn();
    vi.stubGlobal('EventSource', vi.fn(() => ({
      addEventListener: addEventListenerSpy,
      close: closeSpy,
      onerror: null,
    })));

    const { startLootStream } = await freshImport();
    const stop = startLootStream();
    expect(typeof stop).toBe('function');
    stop();
    expect(closeSpy).toHaveBeenCalledOnce();
    vi.unstubAllGlobals();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('startLootStream is a no-op when EventSource is not defined', async () => {
    const originalEventSource = (globalThis as any).EventSource;
    delete (globalThis as any).EventSource;

    const { startLootStream } = await freshImport();
    const stop = startLootStream();
    expect(typeof stop).toBe('function');
    stop();

    (globalThis as any).EventSource = originalEventSource;
  });
});
