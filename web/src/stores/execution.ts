import { get, writable } from 'svelte/store';

export type ExecutionState = 'idle' | 'loading' | 'success' | 'error';

export type ExecutionMap = Map<string, ExecutionState>;

export const executionMap = writable<ExecutionMap>(
  new Map([
    ['Detect', 'idle'],
    ['Copy', 'idle'],
    ['Execute', 'idle'],
    ['Collect', 'idle'],
    ['Cleanup', 'idle'],
  ]),
);

export function updateExecutionMap(key: string, value: ExecutionState) {
  executionMap.update((oldValue) => oldValue.set(key, value));
}

export function getExecutionValue(key: string) {
  let fetchedExecutionMap = get(executionMap);
  return fetchedExecutionMap.get(key);
}
