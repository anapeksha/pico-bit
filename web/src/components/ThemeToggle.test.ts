import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { theme } from '../stores/theme';
import ThemeToggle from './ThemeToggle.svelte';

describe('ThemeToggle', () => {
  beforeEach(() => {
    theme.set('light');
  });

  afterEach(cleanup);

  it('renders a button', () => {
    render(ThemeToggle);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('aria-label says "Switch to dark mode" when theme is light', () => {
    render(ThemeToggle);
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Switch to dark mode');
  });

  it('aria-label says "Switch to light mode" when theme is dark', () => {
    theme.set('dark');
    render(ThemeToggle);
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Switch to light mode');
  });

  it('aria-pressed is false when theme is light', () => {
    render(ThemeToggle);
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'false');
  });

  it('aria-pressed is true when theme is dark', () => {
    theme.set('dark');
    render(ThemeToggle);
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true');
  });

  it('clicking the button toggles theme to dark', async () => {
    render(ThemeToggle);
    await fireEvent.click(screen.getByRole('button'));
    expect(get(theme)).toBe('dark');
  });

  it('clicking the button twice returns to light', async () => {
    render(ThemeToggle);
    const btn = screen.getByRole('button');
    await fireEvent.click(btn);
    await fireEvent.click(btn);
    expect(get(theme)).toBe('light');
  });
});
