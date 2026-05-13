/**
 * Execution timeline state for binary HID injection.
 *
 * `executionMap` maps each pipeline step name to its current `ExecutionState`.
 * Steps progress through `idle → loading → success | error`.
 *
 * `startExecutionStream` opens an SSE connection to `/api/execution/stream`,
 * resets all steps to `idle`, then updates the map on every `execution` event.
 * The connection closes on a `done` event or on SSE error.
 * Calling `startExecutionStream` again while a stream is open replaces it —
 * the previous connection is closed first via `stopExecutionStream`.
 */
import { writable } from 'svelte/store';

export type ExecutionState = 'idle' | 'loading' | 'success' | 'error';
export type ExecutionMap = Map<string, ExecutionState>;

const STEPS = ['Detect', 'Copy', 'Execute', 'Collect', 'Cleanup'] as const;

/** Map of pipeline step name → current execution state. */
export const executionMap = writable<ExecutionMap>(
  new Map(STEPS.map((s) => [s, 'idle' as ExecutionState])),
);

/**
 * Update a single step in `executionMap`.
 * Always produces a new `Map` reference so Svelte's change detection fires.
 */
export function updateExecutionMap(key: string, value: ExecutionState) {
  executionMap.update((m) => new Map(m).set(key, value));
}

/** Reset all steps to `'idle'`. */
export function resetExecution() {
  executionMap.set(new Map(STEPS.map((s) => [s, 'idle' as ExecutionState])));
}

let executionStream: EventSource | null = null;

/**
 * Open (or replace) the SSE stream for the current injection session.
 * Resets all steps to `'idle'` before connecting.
 * Returns `stopExecutionStream` as a teardown function.
 */
export function startExecutionStream(): () => void {
  stopExecutionStream();
  resetExecution();

  if (typeof EventSource === 'undefined') return stopExecutionStream;

  executionStream = new EventSource('/api/execution/stream');

  executionStream.addEventListener('execution', (e: MessageEvent) => {
    try {
      const { step, state } = JSON.parse(e.data) as { step: string; state: ExecutionState };
      updateExecutionMap(step, state);
    } catch {
      // Ignore malformed frames.
    }
  });

  executionStream.addEventListener('done', () => {
    stopExecutionStream();
  });

  executionStream.onerror = () => {
    stopExecutionStream();
  };

  return stopExecutionStream;
}

/** Close the active execution SSE connection if one is open. */
export function stopExecutionStream() {
  executionStream?.close();
  executionStream = null;
}
