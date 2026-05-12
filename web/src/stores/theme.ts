import { writable } from 'svelte/store';

type Theme = 'dark' | 'light';

const STORAGE_KEY = 'picobit-theme';

export const theme = writable<Theme>('light');

function savedTheme(): Theme {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

function applyTheme(next: Theme) {
  document.documentElement.classList.toggle('dark', next === 'dark');
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // Storage can be unavailable in privacy modes; class state still applies.
  }
}

export function initTheme() {
  theme.set(savedTheme());
  return theme.subscribe(applyTheme);
}

export function toggleTheme() {
  theme.update((current) => (current === 'dark' ? 'light' : 'dark'));
}

