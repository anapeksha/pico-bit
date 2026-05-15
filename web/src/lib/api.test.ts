import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { requestJson, uploadBinaryFile } from './api';
import type { RequestFailure } from './types';

function okResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

function errResponse(status: number, body: unknown): Response {
  return {
    ok: false,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

function badJsonResponse(status: number): Response {
  return {
    ok: false,
    status,
    json: vi.fn().mockRejectedValue(new SyntaxError('bad json')),
  } as unknown as Response;
}

describe('requestJson', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns parsed JSON on 200', async () => {
    const payload = { message: 'ok', value: 42 };
    vi.mocked(fetch).mockResolvedValueOnce(okResponse(payload));

    const result = await requestJson('/api/test');
    expect(result).toEqual(payload);
  });

  it('throws RequestFailure with status on non-ok response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(404, { message: 'not found' }));

    await expect(requestJson('/api/missing')).rejects.toMatchObject({
      message: 'not found',
      status: 404,
    });
  });

  it('attaches data to RequestFailure', async () => {
    const body = { message: 'forbidden', code: 'AUTH_REQUIRED' };
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(403, body));

    let caught: RequestFailure | null = null;
    try {
      await requestJson('/api/protected');
    } catch (err) {
      caught = err as RequestFailure;
    }
    expect(caught).not.toBeNull();
    expect(caught!.status).toBe(403);
    expect(caught!.data).toEqual(body);
  });

  it('uses a generic message when JSON body has none', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(500, {}));

    await expect(requestJson('/api/crash')).rejects.toMatchObject({
      message: 'Request failed.',
      status: 500,
    });
  });

  it('handles malformed JSON by treating body as empty and still throwing on non-ok', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(badJsonResponse(503));

    const err = (await requestJson('/api/bad').catch((e) => e)) as RequestFailure;
    expect(err.status).toBe(503);
    expect(err.data).toEqual({});
  });

  it('forwards Content-Type header on every call', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse({}));

    await requestJson('/api/test', { method: 'POST' });
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init as RequestInit).headers).toMatchObject({
      'Content-Type': 'application/json',
    });
  });

  it('merges caller-supplied headers with Content-Type', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse({}));

    await requestJson('/api/test', { headers: { 'X-Custom': 'yes' } });
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init as RequestInit).headers).toMatchObject({
      'Content-Type': 'application/json',
      'X-Custom': 'yes',
    });
  });
});

describe('uploadBinaryFile', () => {
  const xhrMock = {
    open: vi.fn(),
    setRequestHeader: vi.fn(),
    send: vi.fn(),
    upload: { addEventListener: vi.fn() },
    addEventListener: vi.fn(),
    status: 200,
    responseText: '{"ok":true}',
  };

  beforeEach(() => {
    vi.stubGlobal(
      'XMLHttpRequest',
      vi.fn(function () {
        return xhrMock;
      }),
    );
    xhrMock.open.mockClear();
    xhrMock.setRequestHeader.mockClear();
    xhrMock.send.mockClear();
    xhrMock.upload.addEventListener.mockClear();
    xhrMock.addEventListener.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('resolves with parsed JSON on success', async () => {
    xhrMock.addEventListener.mockImplementation((event: string, cb: () => void) => {
      if (event === 'load') cb();
    });
    xhrMock.status = 200;
    xhrMock.responseText = '{"binary":"stored"}';

    const file = new File(['data'], 'payload.exe');
    const result = await uploadBinaryFile(file, vi.fn());
    expect(result).toEqual({ binary: 'stored' });
  });

  it('rejects with RequestFailure on non-2xx status', async () => {
    xhrMock.addEventListener.mockImplementation((event: string, cb: () => void) => {
      if (event === 'load') cb();
    });
    xhrMock.status = 400;
    xhrMock.responseText = '{"message":"bad file"}';

    const file = new File(['data'], 'bad.exe');
    const err = (await uploadBinaryFile(file, vi.fn()).catch((e) => e)) as RequestFailure;
    expect(err.status).toBe(400);
    expect(err.message).toBe('bad file');
  });

  it('rejects with connection error on XHR error event', async () => {
    xhrMock.addEventListener.mockImplementation((event: string, cb: () => void) => {
      if (event === 'error') cb();
    });

    const file = new File(['data'], 'payload.exe');
    await expect(uploadBinaryFile(file, vi.fn())).rejects.toThrow('connection error');
  });

  it('calls onProgress when upload progress events fire', async () => {
    const onProgress = vi.fn();
    xhrMock.upload.addEventListener.mockImplementation(
      (_event: string, cb: (e: ProgressEvent) => void) => {
        cb({ lengthComputable: true, loaded: 50, total: 100 } as ProgressEvent);
      },
    );
    xhrMock.addEventListener.mockImplementation((event: string, cb: () => void) => {
      if (event === 'load') cb();
    });
    xhrMock.status = 200;
    xhrMock.responseText = '{}';

    const file = new File(['data'], 'payload.exe');
    await uploadBinaryFile(file, onProgress);
    expect(onProgress).toHaveBeenCalledWith(50);
  });

  it('opens POST to /api/upload_binary with correct headers', async () => {
    xhrMock.addEventListener.mockImplementation((event: string, cb: () => void) => {
      if (event === 'load') cb();
    });
    xhrMock.status = 200;
    xhrMock.responseText = '{}';

    const file = new File(['data'], 'agent.elf');
    await uploadBinaryFile(file, vi.fn());
    expect(xhrMock.open).toHaveBeenCalledWith('POST', '/api/upload_binary', true);
    expect(xhrMock.setRequestHeader).toHaveBeenCalledWith('X-Filename', 'agent.elf');
    expect(xhrMock.setRequestHeader).toHaveBeenCalledWith(
      'Content-Type',
      'application/octet-stream',
    );
  });
});
