import type { LootRecord } from './types';

export const TRACKING_KEYS = new Set([
  'execution_failure_reason',
  'execution_state',
  'execution_step',
  'source',
  'target_os',
  'timestamp',
]);

export function hasAgentData(record: Record<string, unknown> | null): boolean {
  if (!record) return false;
  return Object.keys(record).some((k) => !TRACKING_KEYS.has(k));
}

export function agentData(record: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(record)) {
    if (!TRACKING_KEYS.has(k)) out[k] = v;
  }
  return out;
}

export type LootRow = {
  label: string;
  mono?: boolean;
  value: string;
};

export type LootSection = {
  rows: LootRow[];
  title: string;
};

function asArray(value: unknown): any[] {
  return Array.isArray(value) ? value : [];
}

function present(value: unknown): boolean {
  return value !== undefined && value !== null && value !== '';
}

function titleCase(value: unknown): string {
  return String(value || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatUptime(seconds: unknown): string {
  const total = Number(seconds || 0);
  if (!total) return '';
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  if (days) return `${days}d ${hours}h`;
  return `${hours || Math.floor(total / 60)}${hours ? 'h' : 'm'}`;
}

function formatMemory(system: Record<string, any>): string {
  if (!present(system.total_mem_mb)) return '';
  const used = Number(system.used_mem_mb || 0);
  const total = Number(system.total_mem_mb || 0);
  if (!total) return '';
  return used ? `${used} / ${total} MB` : `${total} MB`;
}

function formatLootTime(value: unknown): string {
  if (!present(value)) return '';
  const timestamp = Number(value);
  if (!Number.isFinite(timestamp)) return String(value);
  if (timestamp > 1_000_000_000_000) return new Date(timestamp).toLocaleString();
  if (timestamp > 1_000_000_000) return new Date(timestamp * 1000).toLocaleString();
  return `${timestamp} ms`;
}

function row(label: string, value: unknown, mono = false): LootRow | null {
  if (!present(value)) return null;
  return { label, mono, value: String(value) };
}

function section(title: string, rows: Array<LootRow | null>): LootSection | null {
  const visibleRows = rows.filter(Boolean) as LootRow[];
  if (!visibleRows.length) return null;
  return { rows: visibleRows, title };
}

function listSection(title: string, values: unknown[], limit = 6): LootSection | null {
  const rows = asArray(values)
    .slice(0, limit)
    .map((value) => row(String(value), ''));
  const hidden = asArray(values).length - rows.length;
  if (hidden > 0) rows.push(row(`+${hidden} more`, ''));
  return section(title, rows);
}

export function lootSections(data: LootRecord | null): LootSection[] {
  if (!data) return [];

  const type = data.type || 'recon';
  const system = data.system || {};
  const user = data.user || {};
  const osLabel = [system.os_name, system.os_version].filter(Boolean).join(' ');
  const wifi = asArray(data.wifi);
  const interfaces = asArray(data.interfaces);
  const software = asArray(data.software);
  const processes = asArray(data.processes);
  const secrets = asArray(data.env_secrets);
  const sshKeys = asArray(data.ssh_keys);
  const browserPaths = asArray(data.browser_paths);
  const shellHistory = asArray(data.shell_history);

  return [
    section('Collection', [
      row('Type', titleCase(type)),
      row('Source', titleCase(data.source || 'usb_drive')),
      row('Seen', formatLootTime(data.timestamp)),
    ]),
    section('Host', [
      row('Host', system.hostname),
      row('OS', osLabel),
      row('Kernel', system.kernel),
      row('Arch', system.arch),
      row('Memory', formatMemory(system)),
      row('Uptime', formatUptime(system.uptime_secs)),
    ]),
    section('User', [
      row('Name', user.username),
      row('Home', user.home_dir, true),
      row('Elevated', present(user.is_elevated) ? (user.is_elevated ? 'Yes' : 'No') : ''),
    ]),
    section('Inventory', [
      row('Processes', processes.length),
      row('Interfaces', interfaces.length),
      row('WiFi profiles', wifi.length),
      row('Software', software.length),
      row('Env secrets', secrets.length),
      row('SSH keys', sshKeys.length),
      row('Browser DBs', browserPaths.length),
      row('Shell history', shellHistory.length ? `${shellHistory.length} lines` : ''),
    ]),
    section('Result', [
      row('Persistence', present(data.installed) ? (data.installed ? 'Installed' : 'Failed') : ''),
      row('Items wiped', data.items_wiped),
    ]),
    section(
      `WiFi Profiles (${wifi.length})`,
      wifi.slice(0, 8).map((item) => row(item.ssid || '?', item.password || '-', true)),
    ),
    listSection(
      `Interfaces (${interfaces.length})`,
      interfaces.map((item) => item.name || item),
    ),
    section(
      `Software (${software.length})`,
      software.slice(0, 6).map((item) => {
        if (typeof item === 'string') return row(item, '');
        return item.version ? row(item.name || '?', item.version) : row(item.name || '?', '');
      }),
    ),
    section(
      `Env Secrets (${secrets.length})`,
      secrets.slice(0, 8).map((item) => row(item.key || '', item.value || '', true)),
    ),
    section(
      `SSH Keys (${sshKeys.length})`,
      sshKeys.map((item) => row(item.file || '', item.content ? 'Present' : 'Empty')),
    ),
    listSection(
      `Browser DBs (${browserPaths.length})`,
      browserPaths.map((item) => String(item).split(/[/\\]/).slice(-2).join('/')),
      8,
    ),
    shellHistory.length
      ? { rows: [{ label: `${shellHistory.length} lines`, value: '' }], title: 'Shell History' }
      : null,
  ].filter(Boolean) as LootSection[];
}
