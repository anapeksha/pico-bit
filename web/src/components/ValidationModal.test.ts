import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { validation } from '../stores/editor';
import { validationModalOpen } from '../stores/ui';
import ValidationModal from './ValidationModal.svelte';

const ERROR_DIAGNOSTIC = {
  severity: 'error' as const,
  line: 3,
  column: 1,
  end_column: 10,
  message: 'Unknown command: TYPO',
  code: 'parse_error',
};

const WARN_DIAGNOSTIC = {
  severity: 'warning' as const,
  line: 5,
  column: 1,
  end_column: 6,
  message: 'RD_KBD is ignored at runtime',
  hint: 'Use the portal keyboard selector instead.',
  code: 'layout_managed',
};

function makeValidation(
  overrides: Partial<typeof validation extends { set: (v: infer V) => void } ? V : never> = {},
) {
  return {
    blocking: false,
    can_run: true,
    can_save: true,
    badge_label: 'OK',
    badge_tone: 'quiet' as const,
    notice: 'quiet' as const,
    summary: 'OK',
    diagnostics: [],
    ...overrides,
  };
}

describe('ValidationModal', () => {
  beforeEach(() => {
    validationModalOpen.set(false);
    validation.set(null);
  });

  afterEach(cleanup);

  it('renders nothing when modal is closed', () => {
    render(ValidationModal);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders the dialog when modal is open', () => {
    validationModalOpen.set(true);
    render(ValidationModal);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('dialog has the correct aria-label', () => {
    validationModalOpen.set(true);
    render(ValidationModal);
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true');
  });

  it('shows "Validation issues" heading', () => {
    validationModalOpen.set(true);
    render(ValidationModal);
    expect(screen.getByText('Validation issues')).toBeInTheDocument();
  });

  it('subtitle says "Errors found" when validation is blocking', () => {
    validationModalOpen.set(true);
    validation.set(makeValidation({ blocking: true }));
    render(ValidationModal);
    expect(screen.getByText('Errors found in the payload')).toBeInTheDocument();
  });

  it('subtitle says "Payload warnings" when validation is non-blocking', () => {
    validationModalOpen.set(true);
    validation.set(makeValidation({ blocking: false }));
    render(ValidationModal);
    expect(screen.getByText('Payload warnings')).toBeInTheDocument();
  });

  it('renders an error diagnostic with its message', () => {
    validationModalOpen.set(true);
    validation.set(makeValidation({ diagnostics: [ERROR_DIAGNOSTIC] }));
    render(ValidationModal);
    expect(screen.getByText('Unknown command: TYPO')).toBeInTheDocument();
  });

  it('renders line and column for each diagnostic', () => {
    validationModalOpen.set(true);
    validation.set(makeValidation({ diagnostics: [ERROR_DIAGNOSTIC] }));
    render(ValidationModal);
    expect(screen.getByText('Line 3, column 1')).toBeInTheDocument();
  });

  it('renders hint text when present', () => {
    validationModalOpen.set(true);
    validation.set(makeValidation({ diagnostics: [WARN_DIAGNOSTIC] }));
    render(ValidationModal);
    expect(screen.getByText('Use the portal keyboard selector instead.')).toBeInTheDocument();
  });

  it('renders "No issues detected" when diagnostics are empty', () => {
    validationModalOpen.set(true);
    validation.set(makeValidation({ diagnostics: [] }));
    render(ValidationModal);
    expect(screen.getByText('No issues detected.')).toBeInTheDocument();
  });

  it('X button closes the modal', async () => {
    validationModalOpen.set(true);
    render(ValidationModal);
    await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    const { get } = await import('svelte/store');
    expect(get(validationModalOpen)).toBe(false);
  });

  it('backdrop button closes the modal', async () => {
    validationModalOpen.set(true);
    render(ValidationModal);
    await fireEvent.click(screen.getByRole('button', { name: 'Close validation modal' }));
    const { get } = await import('svelte/store');
    expect(get(validationModalOpen)).toBe(false);
  });

  it('Escape keydown closes the modal', async () => {
    validationModalOpen.set(true);
    render(ValidationModal);
    const dialog = screen.getByRole('dialog').parentElement!;
    await fireEvent.keyDown(dialog, { key: 'Escape' });
    const { get } = await import('svelte/store');
    expect(get(validationModalOpen)).toBe(false);
  });

  it('renders multiple diagnostics', () => {
    validationModalOpen.set(true);
    validation.set(makeValidation({ diagnostics: [ERROR_DIAGNOSTIC, WARN_DIAGNOSTIC] }));
    render(ValidationModal);
    expect(screen.getByText('Unknown command: TYPO')).toBeInTheDocument();
    expect(screen.getByText('RD_KBD is ignored at runtime')).toBeInTheDocument();
  });
});
