import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { loot } from '../stores/loot';
import LootViewer from './LootViewer.svelte';

const TRACKING_ONLY = {
  source: 'usb_drive',
  timestamp: 1747123456,
  target_os: 'linux',
  execution_state: 'success',
  execution_step: 'Done',
  execution_failure_reason: null,
};

const WITH_AGENT_DATA = {
  ...TRACKING_ONLY,
  system: { hostname: 'target-host', os_name: 'Ubuntu' },
  user: { username: 'jdoe' },
};

describe('LootViewer', () => {
  beforeEach(() => {
    loot.set(null);
  });

  afterEach(cleanup);

  it('renders nothing when loot is null', () => {
    render(LootViewer);
    expect(screen.queryByRole('pre')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Loot JSON output')).not.toBeInTheDocument();
  });

  it('renders nothing when loot has only tracking keys', () => {
    loot.set(TRACKING_ONLY);
    render(LootViewer);
    expect(screen.queryByLabelText('Loot JSON output')).not.toBeInTheDocument();
  });

  it('renders the JSON output element when loot has agent data', () => {
    loot.set(WITH_AGENT_DATA);
    render(LootViewer);
    expect(screen.getByLabelText('Loot JSON output')).toBeInTheDocument();
  });

  it('JSON output includes hostname value', () => {
    loot.set(WITH_AGENT_DATA);
    render(LootViewer);
    const pre = screen.getByLabelText('Loot JSON output');
    expect(pre.textContent).toContain('target-host');
  });

  it('JSON output includes username value', () => {
    loot.set(WITH_AGENT_DATA);
    render(LootViewer);
    const pre = screen.getByLabelText('Loot JSON output');
    expect(pre.textContent).toContain('jdoe');
  });

  it('does not include tracking-only keys in the rendered output', () => {
    loot.set(WITH_AGENT_DATA);
    render(LootViewer);
    const pre = screen.getByLabelText('Loot JSON output');
    expect(pre.textContent).not.toContain('"source"');
    expect(pre.textContent).not.toContain('"timestamp"');
  });

});
