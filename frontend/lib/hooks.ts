"use client";
import { useCallback, useState } from "react";
import useSWR, { useSWRConfig, type SWRConfiguration } from "swr";
import { ApiError } from "@/lib/api/errors";

/** Cached read. A null key waits. */
export function useData<T>(key: readonly unknown[] | null, load: () => Promise<T>, options?: SWRConfiguration<T, ApiError>) {
  return useSWR<T, ApiError>(key, load, {
    revalidateOnFocus: false,
    keepPreviousData: true,
    shouldRetryOnError: (error) => error.status === 0 || error.status === 503,
    errorRetryCount: 3,
    ...options,
  });
}

/** A write: pending and error state, and every cached read refreshed afterwards so nothing stale stays on screen. */
export function useAction() {
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const { mutate } = useSWRConfig();
  const run = useCallback(async <T,>(name: string, work: () => Promise<T>): Promise<T | undefined> => {
    setPending(name);
    setError(null);
    try {
      return await work();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem : new ApiError(0, "UNEXPECTED", "Something went wrong."));
      return undefined;
    } finally {
      await mutate(() => true); // also after a failure: the backend may have recorded it
      setPending(null);
    }
  }, [mutate]);
  return { run, pending, error, clear: () => setError(null) };
}
