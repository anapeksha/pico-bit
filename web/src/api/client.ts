import type {
  ArmoryMutationResponse,
  ArmoryListResponse,
  BootstrapState,
  HydratedBootstrapState,
  KeyboardTargetResponse,
  KeyboardTargetRequest,
  PayloadReadResponse,
  PayloadMutationResponse,
  PayloadRunResponse,
  PayloadWriteRequest,
  RequestFailure,
  RunsResponse,
} from './contracts';

type JsonObject = Record<string, unknown>;

function asJsonObject(value: unknown): JsonObject {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonObject) : {};
}

function messageFrom(data: JsonObject, fallback: string) {
  return typeof data.message === 'string' ? data.message : fallback;
}

export async function requestJson<T = JsonObject>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });

  let data: JsonObject;
  try {
    data = asJsonObject(await response.json());
  } catch {
    data = {};
  }

  if (!response.ok) {
    const error = new Error(messageFrom(data, 'Request failed.')) as RequestFailure;
    error.data = data;
    error.status = response.status;
    throw error;
  }

  return data as T;
}

export function getBootstrap(): Promise<BootstrapState> {
  return requestJson<BootstrapState>('/api/bootstrap');
}

export function getArmory(): Promise<ArmoryListResponse> {
  return requestJson<ArmoryListResponse>('/api/armory');
}

export function getPayload(): Promise<PayloadReadResponse> {
  return requestJson<PayloadReadResponse>('/api/payload');
}

export function getRuns(): Promise<RunsResponse> {
  return requestJson<RunsResponse>('/api/runs');
}

export async function getHydratedBootstrap(): Promise<HydratedBootstrapState> {
  const bootstrap = await getBootstrap();
  const armory = await getArmory();
  const payload = await getPayload();
  const runs = await getRuns();

  return {
    ...bootstrap,
    files: armory.files.map((file) => ({
      kind: file.kind,
      name: file.name,
      path: file.kind === 'ducky' ? '/payload.dd' : `/api/armory/${encodeURIComponent(file.name)}`,
      size: file.size,
    })),
    payload: payload.code,
    payload_file: 'payload.dd',
    run_history: runs.run_history,
    seeded: runs.seeded,
  };
}

export function savePayload(body: PayloadWriteRequest): Promise<PayloadMutationResponse> {
  return requestJson<PayloadMutationResponse>('/api/payload', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function runPayload(): Promise<PayloadRunResponse> {
  return requestJson<PayloadRunResponse>('/api/payload/run', {
    method: 'POST',
  });
}

export function updateKeyboardTarget(body: KeyboardTargetRequest): Promise<KeyboardTargetResponse> {
  return requestJson<KeyboardTargetResponse>('/api/keyboard/layout', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function uploadBinaryFile(
  file: File,
  onProgress: (percent: number) => void,
): Promise<ArmoryMutationResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/armory/upload/${encodeURIComponent(file.name)}`, true);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      let data: Partial<ArmoryMutationResponse> & { message?: string };
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = {};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as ArmoryMutationResponse);
        return;
      }
      const error = new Error(data.message || 'Upload failed.') as RequestFailure;
      error.data = data;
      error.status = xhr.status;
      reject(error);
    });

    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed — connection error.'));
    });

    xhr.send(file);
  });
}

export function deleteBinaryFile(filename: string): Promise<ArmoryMutationResponse> {
  return requestJson<ArmoryMutationResponse>(`/api/armory/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
}
