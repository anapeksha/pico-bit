import { describe, expect, it } from 'vitest';
import { formatBytes, validateArmoryFile } from './binary';

function makeFile(name: string, bytes: number[], type = 'application/octet-stream'): File {
  return new File([new Uint8Array(bytes)], name, { type });
}

const ELF_MAGIC = [0x7f, 0x45, 0x4c, 0x46, 0x00, 0x00, 0x00, 0x00];
const PE_MAGIC = [0x4d, 0x5a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00];
const MACH_O_MAGIC = [0xfe, 0xed, 0xfa, 0xce, 0x00, 0x00, 0x00, 0x00];
const PLAIN_TEXT = [0x68, 0x65, 0x6c, 0x6c, 0x6f, 0x00, 0x00, 0x00];

describe('formatBytes', () => {
  it('returns bytes label for values under 1 KB', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(1023)).toBe('1023 B');
  });

  it('returns KB label for values between 1 KB and 1 MB', () => {
    expect(formatBytes(1024)).toBe('1.0 KB');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(1536)).toBe('1.5 KB');
  });

  it('returns MB label for values 1 MB and above', () => {
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB');
    expect(formatBytes(2.5 * 1024 * 1024)).toBe('2.5 MB');
  });
});

describe('validateArmoryFile', () => {
  it('rejects null', async () => {
    const err = await validateArmoryFile(null);
    expect(err).not.toBe('');
  });

  it('rejects empty file', async () => {
    const file = new File([], 'empty.exe');
    const err = await validateArmoryFile(file);
    expect(err).not.toBe('');
  });

  it('accepts a valid ELF binary with no extension', async () => {
    const file = makeFile('agent', ELF_MAGIC);
    expect(await validateArmoryFile(file)).toBe('');
  });

  it('accepts a valid ELF binary with .elf extension', async () => {
    const file = makeFile('agent.elf', ELF_MAGIC);
    expect(await validateArmoryFile(file)).toBe('');
  });

  it('accepts a valid PE binary (.exe)', async () => {
    const file = makeFile('payload.exe', PE_MAGIC);
    expect(await validateArmoryFile(file)).toBe('');
  });

  it('accepts a valid PE binary (.bin)', async () => {
    const file = makeFile('payload.bin', PE_MAGIC);
    expect(await validateArmoryFile(file)).toBe('');
  });

  it('accepts a Mach-O binary (32-bit big-endian)', async () => {
    const file = makeFile('agent', MACH_O_MAGIC);
    expect(await validateArmoryFile(file)).toBe('');
  });

  it('rejects a file with a disallowed extension (.py)', async () => {
    const file = makeFile('script.py', ELF_MAGIC);
    const err = await validateArmoryFile(file);
    expect(err).not.toBe('');
  });

  it('rejects a file with a disallowed extension (.sh)', async () => {
    const file = makeFile('run.sh', ELF_MAGIC);
    const err = await validateArmoryFile(file);
    expect(err).not.toBe('');
  });

  it('rejects a file with an image MIME type', async () => {
    const file = makeFile('image.exe', ELF_MAGIC, 'image/png');
    const err = await validateArmoryFile(file);
    expect(err).not.toBe('');
  });

  it('rejects a file with a text MIME type', async () => {
    const file = makeFile('script', PLAIN_TEXT, 'text/plain');
    const err = await validateArmoryFile(file);
    expect(err).not.toBe('');
  });

  it('rejects a zip archive by MIME type', async () => {
    const file = makeFile('archive.exe', PE_MAGIC, 'application/zip');
    const err = await validateArmoryFile(file);
    expect(err).not.toBe('');
  });

  it('rejects a file whose bytes do not match any binary magic', async () => {
    const file = makeFile('not-a-binary', PLAIN_TEXT);
    const err = await validateArmoryFile(file);
    expect(err).not.toBe('');
  });

  it('accepts .appimage extension with ELF magic', async () => {
    const file = makeFile('app.appimage', ELF_MAGIC);
    expect(await validateArmoryFile(file)).toBe('');
  });
});
