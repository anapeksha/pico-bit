import { describe, expect, it } from 'vitest';
import { lootSections } from './loot';

describe('lootSections', () => {
  it('returns empty array for null', () => {
    expect(lootSections(null)).toEqual([]);
  });

  it('returns a Collection section with type and source', () => {
    const sections = lootSections({ type: 'recon', source: 'usb_drive', timestamp: 1747123456 });
    const collection = sections.find((s) => s.title === 'Collection');
    expect(collection).toBeDefined();
    const labels = collection!.rows.map((r) => r.label);
    expect(labels).toContain('Type');
    expect(labels).toContain('Source');
  });

  it('returns a Host section when system data is present', () => {
    const data = {
      system: {
        hostname: 'target-host',
        os_name: 'Ubuntu',
        os_version: '22.04',
        kernel: '5.15.0',
        arch: 'x86_64',
        total_mem_mb: 8192,
        used_mem_mb: 3421,
        uptime_secs: 86712,
      },
    };
    const sections = lootSections(data);
    const host = sections.find((s) => s.title === 'Host');
    expect(host).toBeDefined();
    const rowMap = Object.fromEntries(host!.rows.map((r) => [r.label, r.value]));
    expect(rowMap['Host']).toBe('target-host');
    expect(rowMap['OS']).toBe('Ubuntu 22.04');
    expect(rowMap['Memory']).toBe('3421 / 8192 MB');
  });

  it('formats uptime in days+hours when ≥1 day', () => {
    const data = { system: { hostname: 'h', total_mem_mb: 1, uptime_secs: 86712 } };
    const sections = lootSections(data);
    const host = sections.find((s) => s.title === 'Host');
    const uptime = host?.rows.find((r) => r.label === 'Uptime');
    expect(uptime?.value).toMatch(/^\d+d \d+h$/);
  });

  it('returns a WiFi Profiles section with SSIDs and passwords', () => {
    const data = {
      wifi: [
        { ssid: 'HomeNet', password: 'secret1' },
        { ssid: 'OfficeNet', password: 'secret2' },
      ],
    };
    const sections = lootSections(data);
    const wifiSection = sections.find((s) => s.title.startsWith('WiFi'));
    expect(wifiSection).toBeDefined();
    expect(wifiSection!.rows.map((r) => r.label)).toContain('HomeNet');
    expect(wifiSection!.rows.map((r) => r.label)).toContain('OfficeNet');
  });

  it('returns no WiFi section when wifi array is empty', () => {
    const data = { wifi: [] };
    const sections = lootSections(data);
    const wifiSection = sections.find((s) => s.title.startsWith('WiFi'));
    expect(wifiSection).toBeUndefined();
  });

  it('returns Env Secrets section for env_secrets', () => {
    const data = {
      env_secrets: [{ key: 'AWS_KEY', value: 'AKIA...' }],
    };
    const sections = lootSections(data);
    const secrets = sections.find((s) => s.title.startsWith('Env Secrets'));
    expect(secrets).toBeDefined();
    expect(secrets!.rows[0].label).toBe('AWS_KEY');
    expect(secrets!.rows[0].mono).toBe(true);
  });

  it('returns SSH Keys section', () => {
    const data = {
      ssh_keys: [{ file: '/home/jdoe/.ssh/id_rsa', content: '-----BEGIN RSA' }],
    };
    const sections = lootSections(data);
    const sshSection = sections.find((s) => s.title.startsWith('SSH Keys'));
    expect(sshSection).toBeDefined();
    expect(sshSection!.rows[0].label).toBe('/home/jdoe/.ssh/id_rsa');
    expect(sshSection!.rows[0].value).toBe('Present');
  });

  it('returns Shell History section when history is non-empty', () => {
    const data = { shell_history: ['ls -la', 'cat /etc/passwd'] };
    const sections = lootSections(data);
    const histSection = sections.find((s) => s.title === 'Shell History');
    expect(histSection).toBeDefined();
    expect(histSection!.rows[0].label).toMatch('2 lines');
  });

  it('omits Shell History section when history is empty', () => {
    const data = { shell_history: [] };
    const sections = lootSections(data);
    expect(sections.find((s) => s.title === 'Shell History')).toBeUndefined();
  });

  it('handles a sparse record without crashing', () => {
    expect(() => lootSections({ type: 'recon' })).not.toThrow();
  });

  it('Inventory section counts array lengths', () => {
    const data = {
      processes: [{ pid: 1 }, { pid: 2 }],
      wifi: [{ ssid: 'Net' }],
      software: [{ name: 'git' }],
    };
    const sections = lootSections(data);
    const inventory = sections.find((s) => s.title === 'Inventory');
    expect(inventory).toBeDefined();
    const rowMap = Object.fromEntries(inventory!.rows.map((r) => [r.label, r.value]));
    expect(rowMap['Processes']).toBe('2');
    expect(rowMap['WiFi profiles']).toBe('1');
    expect(rowMap['Software']).toBe('1');
  });
});
