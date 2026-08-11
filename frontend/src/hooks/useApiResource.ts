import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '../api/client';
import type { Paginated } from '../api/types';

interface ResourceState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Fetch-on-mount with cancellation and a manual `reload()`.
 * `deps` behaves like a useEffect dependency list.
 */
export function useApiResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
): ResourceState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  // Keep the latest fetcher without making it a dependency, so callers can pass
  // an inline arrow function without causing an infinite loop.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    setLoading(true);
    setError(null);

    fetcherRef
      .current(controller.signal)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err: unknown) => {
        if (!active || controller.signal.aborted) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof ApiError ? err.message : 'Could not reach the server.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return { data, loading, error, reload };
}

/** Convenience wrapper for the paginated list endpoints. */
export function usePaginatedResource<T>(
  fetcher: (signal: AbortSignal) => Promise<Paginated<T>>,
  deps: unknown[] = [],
) {
  const state = useApiResource<Paginated<T>>(fetcher, deps);
  return {
    ...state,
    items: state.data?.results ?? [],
    count: state.data?.count ?? 0,
    totalPages: state.data?.total_pages ?? 1,
  };
}
