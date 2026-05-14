import { mount } from 'svelte';

import App from './App.svelte';
import './index.css';
import { globalError } from './stores/ui';

import.meta.env.DEV && (await import('./dev/mock'));

const target = document.getElementById('app');

if (target) {
  const authState = target.dataset.authState === 'login' ? 'login' : 'portal';

  mount(App, {
    target,
    props: {
      authState,
      message: target.dataset.message || '',
      messageClass: target.dataset.messageClass || 'notice--hidden',
      username: target.dataset.username || '',
    },
  });

  document.getElementById('app-loading')?.remove();
}

window.addEventListener('unhandledrejection', (event) => {
  const err =
    event.reason instanceof Error
      ? event.reason
      : new Error(String(event.reason));
  console.error('Unhandled promise rejection:', err);
  globalError.set({ message: err.message, stack: err.stack });
});

window.onerror = (_message, _source, _line, _col, error) => {
  const err = error instanceof Error ? error : new Error(String(_message));
  console.error('Uncaught error:', err);
  globalError.set({ message: err.message, stack: err.stack });
};
