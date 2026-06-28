import { getHydratedBootstrap } from '../api/client';
import { createResourceCache } from '../api/cache';
import type { HydratedBootstrapState } from '../api/contracts';

type BootstrapBinding = {
  apply(data: HydratedBootstrapState): void;
  capture(): unknown;
  restore(snapshot: unknown): void;
};

const bootstrapCache = createResourceCache(getHydratedBootstrap);
let binding: BootstrapBinding | null = null;

export function configureBootstrapState(next: BootstrapBinding) {
  binding = next;
}

export async function loadCachedBootstrap() {
  const data = await bootstrapCache.get();
  binding?.apply(data);
  return data;
}

export async function refreshBootstrapSource() {
  const data = await bootstrapCache.refresh();
  binding?.apply(data);
  return data;
}

export function setCachedBootstrap(data: HydratedBootstrapState) {
  bootstrapCache.set(data);
  binding?.apply(data);
}

export function invalidateBootstrap() {
  bootstrapCache.invalidate();
}

export async function withOptimisticBootstrap<T>(
  optimisticUpdate: () => void,
  mutation: () => Promise<T>,
): Promise<T> {
  const snapshot = binding?.capture();
  optimisticUpdate();

  let result: T | undefined;
  let mutationError: unknown = null;

  try {
    result = await mutation();
  } catch (error) {
    mutationError = error;
  }

  try {
    await refreshBootstrapSource();
  } catch (error) {
    if (snapshot !== undefined) binding?.restore(snapshot);
    throw error;
  }

  if (mutationError) throw mutationError;
  return result as T;
}
