import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const BOOTSTRAP_DATA = {
  ap_ssid: 'TestNet',
  ap_password: 'pass123',
  seeded: false,
  keyboard_layout: 'US',
  keyboard_os: 'WIN',
  host_hid_active: true,
  ncm_active: true,
  ncm_url: 'http://192.168.7.1',
};

const ARMORY_DATA = {
  files: [
    {
      kind: 'asset',
      name: 'payload.bin',
      path: '/api/armory/payload.bin',
      size: 4096,
      url: '/api/armory/payload.bin',
    },
  ],
  has_binary: true,
};

const PAYLOAD_DATA = {
  code: 'STRING Hello',
};

const RUNS_DATA = {
  run_history: [],
  seeded: false,
};

const METRICS_DATA = {
  last_run_code: 'none',
  littlefs_free_bytes: 900_000,
  staged_binary_bytes: 4096,
  upload_bytes: 4096,
  upload_duration_ms: 120,
};

describe('loadBootstrap', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    vi.stubGlobal(
      'EventSource',
      vi.fn(() => ({
        addEventListener: vi.fn(),
        close: vi.fn(),
        onerror: null,
      })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function setup() {
    const stores = {
      ap: await import('./ap'),
      binary: await import('./binary'),
      keyboard: await import('./keyboard'),
    };
    const { loadBootstrap } = await import('./bootstrap');
    return { stores, loadBootstrap };
  }

  function mockHydration() {
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(BOOTSTRAP_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(ARMORY_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(PAYLOAD_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(RUNS_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(METRICS_DATA),
      } as unknown as Response);
  }

  it('distributes ap_ssid and ap_password to ap store', async () => {
    mockHydration();

    const { stores, loadBootstrap } = await setup();
    await loadBootstrap();

    expect(get(stores.ap.apSsid)).toBe('TestNet');
    expect(get(stores.ap.apPassword)).toBe('pass123');
  });

  it('hydrates armory files from bootstrap data', async () => {
    mockHydration();

    const { stores, loadBootstrap } = await setup();
    await loadBootstrap();

    expect(get(stores.binary.armoryFiles)).toEqual([
      {
        kind: 'asset',
        name: 'payload.bin',
        path: '/api/armory/payload.bin',
        size: 4096,
        url: '/api/armory/payload.bin',
      },
    ]);
    expect(get(stores.binary.armoryMetrics)).toEqual(METRICS_DATA);
  });

  it('throws when /api/bootstrap returns a non-ok response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: vi.fn().mockResolvedValue({ message: 'service unavailable' }),
    } as unknown as Response);

    const { loadBootstrap } = await setup();
    await expect(loadBootstrap()).rejects.toMatchObject({ status: 503 });
  });

  it('uses defaults when optional ap fields are missing', async () => {
    const minimal = { ...BOOTSTRAP_DATA, ap_ssid: undefined, ap_password: undefined };
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(minimal),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(ARMORY_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(PAYLOAD_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(RUNS_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(METRICS_DATA),
      } as unknown as Response);

    const { stores, loadBootstrap } = await setup();
    await loadBootstrap();

    expect(get(stores.ap.apSsid)).toBe('PicoBit');
    expect(get(stores.ap.apPassword)).toBe('Open network');
  });
});
