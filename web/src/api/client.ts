import type {
  ArmoryMutationResponse,
  BootstrapState,
  PayloadMutationResponse,
  PayloadWriteRequest,
  RequestFailure,
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

export function validatePayload(body: PayloadWriteRequest): Promise<PayloadMutationResponse> {
  return requestJson<PayloadMutationResponse>('/api/payload/validate', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function savePayload(body: PayloadWriteRequest): Promise<PayloadMutationResponse> {
  return requestJson<PayloadMutationResponse>('/api/payload', {
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
