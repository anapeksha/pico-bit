import type { RequestFailure } from './types';

export async function requestJson<T = Record<string, any>>(
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

  let data: Record<string, any>;
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    const error = new Error(data.message || 'Request failed.') as RequestFailure;
    error.data = data;
    error.status = response.status;
    throw error;
  }

  return data as T;
}

export function uploadBinaryFile(
  file: File,
  onProgress: (percent: number) => void,
): Promise<Record<string, any>> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload_binary', true);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('X-Filename', file.name);

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      let data: Record<string, any>;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = {};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
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
