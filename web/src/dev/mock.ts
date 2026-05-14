declare const __PICOBIT_PROXY__: boolean;

type MockRecord = Record<string, any>;

const mockWindow = window as Window & { __PICOBIT_DISABLE_MOCKS__?: boolean };
const shouldMock =
  import.meta.env.DEV && !__PICOBIT_PROXY__ && !mockWindow.__PICOBIT_DISABLE_MOCKS__;

if (shouldMock) {
  const originalFetch = window.fetch.bind(window);
  let payload = 'REM Local Vite mock\\nSTRING Hello from Pico Bit\\nENTER\\n';
  let loot: MockRecord | null = null;
  const runs: MockRecord[] = [];
  let staged = false;

  // Artificial latency so skeleton loaders are visible during development.
  const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

  const jsonResponse = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });

  const requestJson = (body: BodyInit | null | undefined): MockRecord =>
    JSON.parse(typeof body === 'string' ? body : '{}');

  const validationFor = (script: string) => ({
    badge_label: script.includes('BAD') ? 'Errors' : 'Ready',
    badge_tone: script.includes('BAD') ? 'error' : 'success',
    blocking: script.includes('BAD'),
    can_run: !script.includes('BAD'),
    can_save: !script.includes('BAD'),
    diagnostics: script.includes('BAD')
      ? [
          {
            column: 1,
            end_column: 4,
            hint: 'The mock validator treats BAD as a syntax error.',
            line: 1,
            message: 'Unknown mock command.',
            severity: 'error',
          },
        ]
      : [],
    notice: script.includes('BAD') ? 'error' : 'success',
    summary: script.includes('BAD') ? 'Fix one payload issue.' : 'Dry run complete.',
  });

  const usbAgent = () => ({
    active: true,
    available: true,
    can_mount: false,
    can_unmount: true,
    filename: staged ? 'payload.bin' : '',
    has_binary: staged,
    message: 'Local Vite mock USB injector.',
    mounted: true,
    state: 'active',
  });

  window.fetch = async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url;
    const method = (options.method || 'GET').toUpperCase();

    if (!url.startsWith('/api/') && url !== '/logout') {
      return originalFetch(input, options);
    }

    if (url === '/api/bootstrap') {
      await delay(1500);
      return jsonResponse({
        ap_password: 'PicoBit24Net',
        ap_ssid: 'PicoBit',
        auth_enabled: true,
        has_binary: staged,
        keyboard_layout: 'US',
        keyboard_layout_code: 'US',
        keyboard_layout_hint: 'Used for typed text and remembered on the device.',
        keyboard_layout_label: 'English (US)',
        keyboard_layouts: [
          { code: 'US', label: 'English (US)' },
          { code: 'FR', label: 'French (FR)' },
        ],
        keyboard_os: 'WIN',
        keyboard_os_code: 'WIN',
        keyboard_oses: [
          { code: 'WIN', label: 'Windows' },
          { code: 'MAC', label: 'macOS' },
          { code: 'LINUX', label: 'Linux' },
        ],
        keyboard_ready: true,
        keyboard_target_label: 'Windows - English (US)',
        payload,
        run_history: runs,
        seeded: false,
        usb_agent: usbAgent(),
        validation: validationFor(payload),
      });
    }

    if (url === '/api/validate' && method === 'POST') {
      const data = requestJson(options.body);
      return jsonResponse({ validation: validationFor(data.payload || '') });
    }

    if (url === '/api/payload' && method === 'POST') {
      const data = requestJson(options.body);
      payload = data.payload || '';
      return jsonResponse({
        message: 'payload.dd saved.',
        notice: 'success',
        validation: validationFor(payload),
      });
    }

    if (url === '/api/run' && method === 'POST') {
      const data = requestJson(options.body);
      payload = data.payload || payload;
      runs.unshift({
        message: 'Mock payload executed.',
        notice: 'success',
        preview: payload.split('\\n').find(Boolean) || 'Empty payload',
        sequence: runs.length + 1,
        source: 'portal',
      });
      return jsonResponse({
        message: 'Mock payload executed.',
        notice: 'success',
        run_history: runs,
        validation: validationFor(payload),
      });
    }

    if (url === '/api/keyboard-layout' && method === 'POST') {
      const data = requestJson(options.body);
      const osLabel = { LINUX: 'Linux', MAC: 'macOS', WIN: 'Windows' }[data.os] || 'Windows';
      return jsonResponse({
        keyboard_layout: data.layout || 'US',
        keyboard_layout_code: data.layout || 'US',
        keyboard_layout_hint: 'Used for typed text and remembered on the device.',
        keyboard_layout_label: data.layout === 'FR' ? 'French (FR)' : 'English (US)',
        keyboard_layouts: [
          { code: 'US', label: 'English (US)' },
          { code: 'FR', label: 'French (FR)' },
        ],
        keyboard_os: data.os || 'WIN',
        keyboard_os_code: data.os || 'WIN',
        keyboard_oses: [
          { code: 'WIN', label: 'Windows' },
          { code: 'MAC', label: 'macOS' },
          { code: 'LINUX', label: 'Linux' },
        ],
        keyboard_target_label: `${osLabel} - ${data.layout === 'FR' ? 'French (FR)' : 'English (US)'}`,
        message: 'Typing target updated in local mock.',
        notice: 'success',
      });
    }

    if (url === '/api/upload_binary' && method === 'POST') {
      staged = true;
      return jsonResponse({
        filename: 'payload.bin',
        message: 'Mock binary uploaded.',
        notice: 'success',
        usb_agent: usbAgent(),
      });
    }

    if (url === '/api/inject_binary' && method === 'POST') {
      runs.unshift({
        message: 'Mock USB stager injected.',
        notice: 'success',
        preview: 'USB agent stager',
        sequence: runs.length + 1,
        source: 'portal',
      });
      return jsonResponse({
        message: 'Mock USB stager injected.',
        notice: 'success',
        run_history: runs,
        usb_agent: usbAgent(),
      });
    }

    if (url === '/api/loot' && method === 'GET') {
      return loot
        ? jsonResponse(loot)
        : jsonResponse({ message: 'No loot collected yet.' }, 404);
    }

    if (url === '/api/loot/import-usb' && method === 'POST') {
      await delay(1200);
      loot = {
        execution_step: 'Cleanup',
        execution_state: 'success',
        execution_failure_reason: null,
        source: 'usb_drive',
        system: { arch: 'arm64', hostname: 'mock-host', os_name: 'macOS' },
        timestamp: Date.now(),
        type: 'recon',
        user: { username: 'analyst' },
      };
      return jsonResponse({ loot, message: 'Mock USB loot imported.', notice: 'success' });
    }

    if (url === '/api/loot/download') {
      return jsonResponse(loot || {});
    }

    return originalFetch(input, options);
  };

  // Execution step sequence emitted by the mock execution stream.
  const MOCK_EXECUTION_STEPS = [
    { step: 'Detect', state: 'loading' },
    { step: 'Detect', state: 'success' },
    { step: 'Copy', state: 'loading' },
    { step: 'Copy', state: 'success' },
    { step: 'Execute', state: 'loading' },
    { step: 'Collect', state: 'success' },
    { step: 'Cleanup', state: 'success' },
  ] as const;

  window.EventSource = class MockEventSource extends EventTarget {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSED = 2;
    readonly CONNECTING = 0;
    readonly OPEN = 1;
    readonly CLOSED = 2;
    readonly readyState = 1;
    readonly withCredentials = false;
    readonly url: string;
    onerror: ((this: EventSource, ev: Event) => any) | null = null;
    onmessage: ((this: EventSource, ev: MessageEvent) => any) | null = null;
    onopen: ((this: EventSource, ev: Event) => any) | null = null;

    private _timers: ReturnType<typeof setTimeout>[] = [];

    constructor(url: string) {
      super();
      this.url = url;

      if (url.includes('/api/execution/stream')) {
        let delay = 400;
        for (const step of MOCK_EXECUTION_STEPS) {
          this._timers.push(
            setTimeout(() => {
              this.dispatchEvent(
                new MessageEvent('execution', { data: JSON.stringify(step) }),
              );
            }, delay),
          );
          delay += 500;
        }
        this._timers.push(
          setTimeout(() => {
            this.dispatchEvent(new MessageEvent('done', { data: '{}' }));
          }, delay),
        );
      }
    }

    close() {
      for (const t of this._timers) clearTimeout(t);
      this._timers = [];
    }
  } as unknown as typeof EventSource;
}
