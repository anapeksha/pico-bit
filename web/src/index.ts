import { mount } from 'svelte';

import App from './App.svelte';
import './index.css';

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

  // App is now rendered — drop the pre-mount spinner.
  document.getElementById('app-loading')?.remove();
}
