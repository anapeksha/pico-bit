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
  let keyboardLayout = 'US';
  let keyboardOs = 'WIN';

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
    root_url: 'http://192.168.7.1',
  });

  const hostHid = () => ({
    active: true,
  });

  const armoryFiles = () => [
    {
      kind: 'ducky',
      name: 'payload.dd',
      size: payload.length,
    },
    ...(staged
      ? [
          {
            kind: 'asset',
            name: 'payload.bin',
            size: 128 * 1024,
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
        host_hid_active: hostHid().active,
        keyboard_layout: keyboardLayout,
        keyboard_os: keyboardOs,
        ncm_active: ncmLink().active,
        ncm_url: ncmLink().root_url,
        seeded: false,
      });
    }

    if (url === '/api/keyboard/layout' && method === 'POST') {
      const data = requestJson(options.body);
      keyboardLayout = stringField(data, 'layout') || keyboardLayout;
      keyboardOs = stringField(data, 'os') || keyboardOs;
      return jsonResponse({
        keyboard_layout: keyboardLayout,
        keyboard_os: keyboardOs,
        message: 'Keyboard target updated.',
        notice: 'success',
      });
    }

    if (url === '/api/payload' && method === 'POST') {
      const data = requestJson(options.body);
      const draft = stringField(data, 'code');
      const validation = validationFor(draft);
      if (!validation.blocking) {
        payload = draft;
      }

      return jsonResponse(
        {
          message: validation.blocking ? validation.summary : 'payload.dd saved.',
          notice: validation.blocking ? 'error' : 'success',
          success: !validation.blocking,
          error_line: validation.diagnostics[0]?.line || null,
        },
        validation.blocking ? 400 : 200,
      );
    }

    if (url === '/api/payload/run' && method === 'POST') {
      const validation = validationFor(payload);
      if (!validation.blocking) {
        runs.unshift({
          ok: true,
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
      });
    }

    if (url === '/api/payload' && method === 'GET') {
      return jsonResponse({ code: payload });
    }

    if (url === '/api/runs' && method === 'GET') {
      return jsonResponse({
        run_history: runs,
        seeded: false,
      });
    }

    if (url.startsWith('/api/armory/upload/') && method === 'POST') {
      staged = true;
      return jsonResponse({
        filename: 'payload.bin',
        has_binary: true,
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
        message: 'Mock file deleted.',
        notice: 'success',
      });
    }

    return originalFetch(input, options);
  };
}
