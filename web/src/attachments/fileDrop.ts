import type { Attachment } from 'svelte/attachments';

type FileDropOptions = {
  /** Called with the first file selected by click, keyboard activation, or drag-and-drop. */
  onFile: (file: File) => void;
};

/**
 * Svelte attachment that turns any element into a file drop zone.
 *
 * The attachment runs inside an effect when the element mounts. It registers
 * click, keyboard, and drag-and-drop listeners, then returns a cleanup function
 * that Svelte calls before the attachment re-runs or the element is removed.
 *
 * Clicking the element (except directly on an `<input>`) forwards the click to
 * the first `<input type="file">` child. Space and Enter do the same for
 * keyboard users. Dragging a file onto the element adds visual highlight
 * classes and calls `onFile` with the first dropped file on release.
 *
 * Usage: `{@attach fileDrop({ onFile: handler })}`
 */
export function fileDrop(options: FileDropOptions): Attachment<HTMLElement> {
  return (node) => {
    function choose(file: File | undefined) {
      if (file) options.onFile(file);
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

    // Returned cleanup is called by Svelte before re-run or element removal.
    return () => {
      node.removeEventListener('click', onClick);
      node.removeEventListener('keydown', onKeydown);
      node.removeEventListener('dragover', onDragover);
      node.removeEventListener('dragleave', onDragleave);
      node.removeEventListener('drop', onDrop);
    };
  };
}
