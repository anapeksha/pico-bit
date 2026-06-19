import { cleanup, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { resetExecution, updateExecutionMap } from '../stores/execution';
import ExecutionTimeline from './ExecutionTimeline.svelte';

const STEPS = ['Detect', 'Copy', 'Execute', 'Collect', 'Cleanup'];

describe('ExecutionTimeline', () => {
  beforeEach(() => {
    resetExecution();
  });

  afterEach(cleanup);

  it('renders an ordered list with the correct aria-label', () => {
    render(ExecutionTimeline);
    expect(screen.getByRole('list')).toHaveAttribute(
      'aria-label',
      'Binary injection execution timeline',
    );
  });

  it('renders exactly 5 list items', () => {
    render(ExecutionTimeline);
    expect(screen.getAllByRole('listitem')).toHaveLength(5);
  });

  it('renders every step label', () => {
    render(ExecutionTimeline);
    for (const step of STEPS) {
      expect(screen.getByText(step)).toBeInTheDocument();
    }
  });

  it('all steps show "planned" state when idle', () => {
    render(ExecutionTimeline);
    const items = screen.getAllByRole('listitem');
    items.forEach((item) => {
      expect(item.getAttribute('aria-label')).toMatch(/planned/);
    });
  });

  it('first step shows "running" when state is loading', async () => {
    render(ExecutionTimeline);
    updateExecutionMap('Detect', 'loading');
    await tick();
    const item = screen.getAllByRole('listitem')[0];
    expect(item.getAttribute('aria-label')).toMatch(/running/);
  });

  it('first step shows "done" when state is success', async () => {
    render(ExecutionTimeline);
    updateExecutionMap('Detect', 'success');
    await tick();
    const item = screen.getAllByRole('listitem')[0];
    expect(item.getAttribute('aria-label')).toMatch(/done/);
  });

  it('first step shows "failed" when state is error', async () => {
    render(ExecutionTimeline);
    updateExecutionMap('Detect', 'error');
    await tick();
    const item = screen.getAllByRole('listitem')[0];
    expect(item.getAttribute('aria-label')).toMatch(/failed/);
  });

  it('step indices in aria-labels start at 1', () => {
    render(ExecutionTimeline);
    const items = screen.getAllByRole('listitem');
    STEPS.forEach((step, i) => {
      expect(items[i].getAttribute('aria-label')).toMatch(new RegExp(`^${i + 1}\\.`));
    });
  });

  it('each step includes its name in the aria-label', () => {
    render(ExecutionTimeline);
    const items = screen.getAllByRole('listitem');
    STEPS.forEach((step, i) => {
      expect(items[i].getAttribute('aria-label')).toContain(step);
    });
  });

  it('pre-set state is reflected immediately on render', () => {
    updateExecutionMap('Copy', 'success');
    render(ExecutionTimeline);
    const copyItem = screen.getAllByRole('listitem')[1];
    expect(copyItem.getAttribute('aria-label')).toMatch(/done/);
  });

  it('resetExecution clears all states back to planned', async () => {
    updateExecutionMap('Execute', 'success');
    render(ExecutionTimeline);
    resetExecution();
    await tick();
    const executeItem = screen.getAllByRole('listitem')[2];
    expect(executeItem.getAttribute('aria-label')).toMatch(/planned/);
  });
});
