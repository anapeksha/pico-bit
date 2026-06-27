declare const __PICOBIT_PROXY__: boolean;

type MockRecord = Record<string, unknown>;

const mockWindow = window as Window & { __PICOBIT_DISABLE_MOCKS__?: boolean };
const shouldMock =
  import.meta.env.DEV && !__PICOBIT_PROXY__ && !mockWindow.__PICOBIT_DISABLE_MOCKS__;

if (shouldMock) {
  const originalFetch = window.fetch.bind(window);
  let payload = 'REM Local Vite mock\\nSTRING Hello from Pico Bit\\nENTER\\n';
  const runs: MockRecord[] = [];
  let staged = false;

  // Artificial latency so skeleton loaders are visible during development.
  const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

  const jsonResponse = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });

  const requestJson = (body: BodyInit | null | undefined): MockRecord => {
    const parsed = JSON.parse(typeof body === 'string' ? body : '{}') as unknown;
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as MockRecord)
      : {};
  };

  const stringField = (data: MockRecord, key: string) =>
    typeof data[key] === 'string' ? data[key] : '';

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

  const ncmLink = () => ({
    active: true,
    address: '192.168.7.1',
    available: true,
    filename: staged ? 'payload.bin' : '',
    gateway: '192.168.7.1',
    has_binary: staged,
    interface: 'usb-ncm',
    message: 'Local Vite mock NCM link.',
    root_url: 'http://192.168.7.1',
    state: 'active',
    transport: 'ncm',
  });

  const hostHid = () => ({
    active: true,
    available: true,
    message: 'Local Vite mock Host HID.',
    state: 'active',
  });

  const armoryFiles = () => [
    {
      kind: 'ducky',
      name: 'payload.dd',
      path: '/payload.dd',
      size: payload.length,
      url: '/payload.dd',
    },
    ...(staged
      ? [
          {
            kind: 'asset',
            name: 'payload.bin',
            path: '/armory/payload.bin',
            size: 128 * 1024,
            url: '/armory/payload.bin',
          },
        ]
      : []),
  ];

  window.fetch = async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url;
    const method = (options.method || 'GET').toUpperCase();

    if (!url.startsWith('/api/')) {
      return originalFetch(input, options);
    }

    if (url === '/api/bootstrap') {
      await delay(1500);
      return jsonResponse({
        ap_password: 'PicoBit24Net',
        ap_ssid: 'PicoBit',
        files: armoryFiles(),
        has_binary: staged,
        host_hid: hostHid(),
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
        keyboard_target_label: 'Windows - English (US)',
        ncm_link: ncmLink(),
        payload,
        run_history: runs,
        seeded: false,
      });
    }

    if (url === '/api/payload/validate' && method === 'POST') {
      const data = requestJson(options.body);
      const validation = validationFor(stringField(data, 'code'));
      return jsonResponse({
        error_line: validation.diagnostics[0]?.line || null,
        message: validation.summary,
        success: !validation.blocking,
      });
    }

    if (url === '/api/payload' && method === 'POST') {
      const data = requestJson(options.body);
      payload = stringField(data, 'code');
      const validation = validationFor(payload);
      return jsonResponse({
        message: 'payload.dd saved.',
        notice: 'success',
        success: !validation.blocking,
        error_line: validation.diagnostics[0]?.line || null,
      });
    }

    if (url === '/api/payload/run' && method === 'POST') {
      const validation = validationFor(payload);
      if (!validation.blocking) {
        runs.unshift({
          message: 'Mock payload run requested.',
          notice: 'success',
          preview: payload.split('\n').find(Boolean) || 'payload.dd',
          sequence: runs.length + 1,
          source: 'payload.dd',
        });
      }

      return jsonResponse(
        {
          message: validation.blocking ? validation.summary : 'Mock payload run requested.',
          success: !validation.blocking,
        },
        validation.blocking ? 400 : 200,
      );
    }

    if (url === '/api/armory' && method === 'GET') {
      return jsonResponse({
        files: armoryFiles(),
        has_binary: staged,
        message: 'Local armory mock.',
        notice: 'quiet',
      });
    }

    if (url.startsWith('/api/armory/upload/') && method === 'POST') {
      staged = true;
      return jsonResponse({
        filename: 'payload.bin',
        has_binary: true,
        max_upload_bytes: 500 * 1024,
        message: 'Mock binary uploaded.',
        notice: 'success',
      });
    }

    if (url.startsWith('/api/armory/') && method === 'DELETE') {
      if (url.endsWith('/payload.dd')) {
        return jsonResponse(
          {
            filename: 'payload.dd',
            has_binary: staged,
            max_upload_bytes: 500 * 1024,
            message: 'payload.dd is managed by the editor and cannot be deleted.',
            notice: 'error',
          },
          403,
        );
      }

      staged = false;
      return jsonResponse({
        filename: decodeURIComponent(url.split('/').pop() || ''),
        has_binary: false,
        max_upload_bytes: 500 * 1024,
        message: 'Mock file deleted.',
        notice: 'success',
      });
    }

    return originalFetch(input, options);
  };
}
