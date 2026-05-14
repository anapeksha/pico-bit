import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const BOOTSTRAP_DATA = {
  ap_ssid: 'TestNet',
  ap_password: 'pass123',
  auth_enabled: true,
  keyboard_ready: true,
  seeded: false,
  has_binary: true,
  run_history: [],
  payload: 'STRING Hello',
  keyboard_layout: 'en-US',
  keyboard_os: 'windows',
  keyboard_layouts: [{ code: 'en-US', label: 'English (US)' }],
  keyboard_oses: [{ code: 'windows', label: 'Windows' }],
  keyboard_layout_label: 'English (US)',
  keyboard_os_label: 'Windows',
  keyboard_target_label: 'Windows / English (US)',
  keyboard_layout_hint: '',
};

describe('loadBootstrap', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    vi.stubGlobal('EventSource', vi.fn(() => ({
      addEventListener: vi.fn(),
      close: vi.fn(),
      onerror: null,
    })));
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

  it('distributes ap_ssid and ap_password to ap store', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(BOOTSTRAP_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: vi.fn().mockResolvedValue({}),
      } as unknown as Response);

    const { stores, loadBootstrap } = await setup();
    await loadBootstrap();

    expect(get(stores.ap.apSsid)).toBe('TestNet');
    expect(get(stores.ap.apPassword)).toBe('pass123');
    expect(get(stores.ap.authEnabled)).toBe(true);
  });

  it('sets hasBinary from bootstrap data', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(BOOTSTRAP_DATA),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: vi.fn().mockResolvedValue({}),
      } as unknown as Response);

    const { stores, loadBootstrap } = await setup();
    await loadBootstrap();

    expect(get(stores.binary.hasBinary)).toBe(true);
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
        ok: false,
        status: 404,
        json: vi.fn().mockResolvedValue({}),
      } as unknown as Response);

    const { stores, loadBootstrap } = await setup();
    await loadBootstrap();

    expect(get(stores.ap.apSsid)).toBe('PicoBit');
    expect(get(stores.ap.apPassword)).toBe('Open network');
  });
});
