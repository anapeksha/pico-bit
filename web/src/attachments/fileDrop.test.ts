import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fileDrop } from './fileDrop';

function makeNode(): HTMLDivElement {
  const node = document.createElement('div');
  const input = document.createElement('input');
  input.type = 'file';
  node.appendChild(input);
  return node;
}

function fireEvent<T extends Event>(node: HTMLElement, event: T): void {
  node.dispatchEvent(event);
}

function makeDragEvent(type: string, files: File[] = []): DragEvent {
  const dt = {
    files: files as unknown as FileList,
    items: [],
    types: files.length ? ['Files'] : [],
  };
  const event = new Event(type, { bubbles: true, cancelable: true }) as unknown as DragEvent;
  Object.defineProperty(event, 'dataTransfer', { value: dt, writable: false });
  return event;
}

describe('fileDrop attachment', () => {
  let node: HTMLDivElement;
  let onFile: ReturnType<typeof vi.fn>;
  let cleanup: (() => void) | void;

  beforeEach(() => {
    node = makeNode();
    onFile = vi.fn();
    const attachment = fileDrop({ onFile });
    cleanup = attachment(node);
  });

  afterEach(() => {
    if (typeof cleanup === 'function') cleanup();
  });

  it('calls onFile when a file is dropped onto the node', () => {
    const file = new File(['content'], 'payload.exe');
    fireEvent(node, makeDragEvent('drop', [file]));
    expect(onFile).toHaveBeenCalledOnce();
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it('does not call onFile when drop has no files', () => {
    fireEvent(node, makeDragEvent('drop', []));
    expect(onFile).not.toHaveBeenCalled();
  });

  it('adds highlight classes on dragover', () => {
    const event = new Event('dragover', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'preventDefault', { value: vi.fn(), writable: true });
    fireEvent(node, event);
    expect(node.classList.contains('border-picobit-text')).toBe(true);
    expect(node.classList.contains('bg-picobit-surface-3')).toBe(true);
  });

  it('removes highlight classes on dragleave', () => {
    node.classList.add('border-picobit-text', 'bg-picobit-surface-3');
    fireEvent(node, new Event('dragleave', { bubbles: true }));
    expect(node.classList.contains('border-picobit-text')).toBe(false);
    expect(node.classList.contains('bg-picobit-surface-3')).toBe(false);
  });

  it('removes highlight classes after drop', () => {
    node.classList.add('border-picobit-text', 'bg-picobit-surface-3');
    const file = new File(['content'], 'agent.elf');
    fireEvent(node, makeDragEvent('drop', [file]));
    expect(node.classList.contains('border-picobit-text')).toBe(false);
    expect(node.classList.contains('bg-picobit-surface-3')).toBe(false);
  });

  it('forwards click to the file input when clicking the container (not the input)', () => {
    const input = node.querySelector<HTMLInputElement>('input[type="file"]')!;
    const inputClick = vi.spyOn(input, 'click');

    const event = new MouseEvent('click', { bubbles: true });
    Object.defineProperty(event, 'target', { value: node, writable: false });
    fireEvent(node, event);

    expect(inputClick).toHaveBeenCalledOnce();
  });

  it('does not forward click when the input itself is clicked', () => {
    const input = node.querySelector<HTMLInputElement>('input[type="file"]')!;
    const inputClick = vi.spyOn(input, 'click');

    const event = new MouseEvent('click', { bubbles: true });
    Object.defineProperty(event, 'target', { value: input, writable: false });
    fireEvent(node, event);

    expect(inputClick).not.toHaveBeenCalled();
  });

  it('forwards Enter key to file input', () => {
    const input = node.querySelector<HTMLInputElement>('input[type="file"]')!;
    const inputClick = vi.spyOn(input, 'click');

    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    fireEvent(node, event);

    expect(inputClick).toHaveBeenCalledOnce();
  });

  it('forwards Space key to file input', () => {
    const input = node.querySelector<HTMLInputElement>('input[type="file"]')!;
    const inputClick = vi.spyOn(input, 'click');

    const event = new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true });
    fireEvent(node, event);

    expect(inputClick).toHaveBeenCalledOnce();
  });

  it('does not react to other keys', () => {
    const input = node.querySelector<HTMLInputElement>('input[type="file"]')!;
    const inputClick = vi.spyOn(input, 'click');

    fireEvent(node, new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(inputClick).not.toHaveBeenCalled();
  });

  it('cleanup removes all event listeners', () => {
    expect(typeof cleanup).toBe('function');
    (cleanup as () => void)();
    cleanup = undefined;

    const file = new File(['content'], 'payload.exe');
    fireEvent(node, makeDragEvent('drop', [file]));
    expect(onFile).not.toHaveBeenCalled();

    node.classList.add('border-picobit-text', 'bg-picobit-surface-3');
    fireEvent(node, new Event('dragleave'));
    expect(node.classList.contains('border-picobit-text')).toBe(true);
  });
});
