import type { Action } from 'svelte/action';

type FileDropOptions = {
  onFile: (file: File) => void;
};

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
