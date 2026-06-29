export function createResourceCache<T>(fetcher: () => Promise<T>) {
  let data: T | null = null;
  let loaded = false;
  let inFlight: Promise<T> | null = null;

  async function read(force = false): Promise<T> {
    if (!force && loaded && data !== null) return data;
    if (!force && inFlight) return inFlight;

    inFlight = fetcher()
      .then((next) => {
        data = next;
        loaded = true;
        return next;
      })
      .finally(() => {
        inFlight = null;
      });

    return inFlight;
  }

  return {
    get: () => read(false),
    refresh: () => read(true),
  };
}
