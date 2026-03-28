// ─── src/hooks/useApi.js ──────────────────────────────────────────────────────
// Generic data-fetching hook — wraps any service method.
//
// Usage:
//   const { data, error, loading, refetch } = useApi(
//     (signal) => supportService.fetchTickets({}, signal),
//     [filter]   // re-fetches when filter changes
//   );

import { useState, useEffect, useCallback, useRef } from "react";

/**
 * @template T
 * @param {(signal: AbortSignal) => Promise<{ data: T, error: string|null }>} fetcher
 * @param {any[]} deps — re-fetch when any dep changes
 * @param {{ immediate?: boolean, initialData?: T }} options
 * @returns {{ data: T|null, error: string|null, loading: boolean, refetch: () => void }}
 */
export function useApi(fetcher, deps = [], { immediate = true, initialData = null } = {}) {
  const [data,    setData]    = useState(initialData);
  const [error,   setError]   = useState(null);
  const [loading, setLoading] = useState(immediate);
  const fetcherRef = useRef(fetcher);

  useEffect(() => { fetcherRef.current = fetcher; });

  const run = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    fetcherRef.current(controller.signal).then(({ data: d, error: e }) => {
      if (controller.signal.aborted) return;
      if (e) setError(e);
      else   setData(d);
      setLoading(false);
    });

    return () => controller.abort();
  }, []);   // eslint-disable-line

  useEffect(() => {
    if (!immediate) return;
    return run();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, refetch: run };
}

/**
 * Mutation hook — for POST/PATCH/DELETE operations.
 *
 * Usage:
 *   const { mutate, loading, error } = useMutation(supportService.createTicket);
 *   const result = await mutate(payload);
 *
 * @template TArgs, TResult
 * @param {(...args: TArgs) => Promise<{ data: TResult, error: string|null }>} mutationFn
 * @returns {{ mutate, loading, error, data }}
 */
export function useMutation(mutationFn) {
  const [data,    setData]    = useState(null);
  const [error,   setError]   = useState(null);
  const [loading, setLoading] = useState(false);
  const fnRef = useRef(mutationFn);

  useEffect(() => { fnRef.current = mutationFn; });

  const mutate = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    const result = await fnRef.current(...args);
    if (result.error) setError(result.error);
    else              setData(result.data);
    setLoading(false);
    return result;
  }, []);

  return { mutate, loading, error, data };
}

export default useApi;
