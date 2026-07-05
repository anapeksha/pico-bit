'use strict';

import { mount } from 'svelte';

import App from './App.svelte';
import './index.css';
import { globalError } from './stores/ui';

if (import.meta.env.DEV) {
  await import('./dev/mock');
}

const target = document.getElementById('app');

if (target) {
  mount(App, {
    target,
  });

  document.getElementById('app-loading')?.remove();
}

window.addEventListener('unhandledrejection', (event) => {
  const err = event.reason instanceof Error ? event.reason : new Error(String(event.reason));
  // eslint-disable-next-line no-console
  console.error('Unhandled promise rejection:', err);
  globalError.set({ message: err.message, stack: err.stack });
});

window.onerror = (_message, _source, _line, _col, error) => {
  const err = error instanceof Error ? error : new Error(String(_message));
  // eslint-disable-next-line no-console
  console.error('Uncaught error:', err);
  globalError.set({ message: err.message, stack: err.stack });
};
