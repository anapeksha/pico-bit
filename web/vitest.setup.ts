import '@testing-library/jest-dom/vitest';

// Polyfill Blob.prototype.arrayBuffer using FileReader, which jsdom implements correctly.
// jsdom's native Blob.arrayBuffer() may throw in some environments.
if (typeof Blob !== 'undefined') {
  Blob.prototype.arrayBuffer = function () {
    return new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(this);
    });
  };
}
