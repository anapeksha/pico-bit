import type { Action } from 'svelte/action';

/**
 * Options accepted by the {@link fileDrop} action.
 */
type FileDropOptions = {
  /** Called with the first file selected by click, keyboard activation, or drag-and-drop. */
  onFile: (file: File) => void;
};

/**
 * Svelte action that turns any element into a file drop zone.
 *
 * Clicking the element (except directly on an `<input>`) forwards the click to
 * the first `<input type="file">` child. Space and Enter do the same for
 * keyboard users. Dragging a file onto the element adds visual highlight
 * classes and calls `options.onFile` with the first dropped file on release.
 */
export const fileDrop: Action<HTMLElement, FileDropOptions> = (node, options) => {
  let current = options;

  function choose(file: File | undefined) {
    if (file) current.onFile(file);
  }

  function onClick(event: MouseEvent) {
    if ((event.target as HTMLElement).tagName !== 'INPUT') {
      node.querySelector<HTMLInputElement>('input[type="file"]')?.click();
    }
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      node.querySelector<HTMLInputElement>('input[type="file"]')?.click();
    }
  }

  function onDragover(event: DragEvent) {
    event.preventDefault();
    node.classList.add('border-picobit-text', 'bg-picobit-surface-3');
  }

  function onDragleave() {
    node.classList.remove('border-picobit-text', 'bg-picobit-surface-3');
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    onDragleave();
    choose(event.dataTransfer?.files?.[0]);
  }

  node.addEventListener('click', onClick);
  node.addEventListener('keydown', onKeydown);
  node.addEventListener('dragover', onDragover);
  node.addEventListener('dragleave', onDragleave);
  node.addEventListener('drop', onDrop);

  return {
    update(next) {
      current = next;
    },
    destroy() {
      node.removeEventListener('click', onClick);
      node.removeEventListener('keydown', onKeydown);
      node.removeEventListener('dragover', onDragover);
      node.removeEventListener('dragleave', onDragleave);
      node.removeEventListener('drop', onDrop);
    },
  };
};
