import { mount } from 'svelte';

import App from './App.svelte';
import './dev/mock';
import './index.css';

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
}
