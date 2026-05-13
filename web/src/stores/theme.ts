/**
 * Theme (dark / light) management backed by `localStorage`.
 *
 * `initTheme` reads the saved preference, applies it to the document root, and
 * returns an unsubscribe function — call it in the component's `onDestroy` / as
 * the return value of `onMount`.
 * `toggleTheme` flips between `'dark'` and `'light'`.
 */
import { writable } from 'svelte/store';

type Theme = 'dark' | 'light';

const STORAGE_KEY = 'picobit-theme';

/** Currently active theme. */
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

/**
 * Initialise the theme from `localStorage` and subscribe to future changes.
 * Returns the Svelte store unsubscribe function — pass it to `onMount` as the
 * cleanup return value.
 */
export function initTheme() {
  theme.set(savedTheme());
  return theme.subscribe(applyTheme);
}

/** Toggle between `'dark'` and `'light'` themes. */
export function toggleTheme() {
  theme.update((current) => (current === 'dark' ? 'light' : 'dark'));
}
