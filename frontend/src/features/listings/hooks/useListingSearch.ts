import { useEffect, useState } from 'react';
import { ApiError, FAILURE_MESSAGES, searchListings } from '../api/listings';
import type { SearchPage } from '../model/schemas';

interface Outcome {
  requestKey: string;
  result: SearchPage | null;
  error: ApiError | null;
}

/** Runs the search whenever the query changes and reports result, loading and error.
 * The previous result stays available while the next one loads.
 */
export function useListingSearch(query: string) {
  const [attempt, setAttempt] = useState(0);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  // `attempt` makes "Try again" a new request even though the query is the same.
  const requestKey = `${query}#${attempt}`;

  useEffect(() => {
    const controller = new AbortController();

    async function load(): Promise<void> {
      let next: Outcome;
      try {
        next = { requestKey, result: await searchListings(query, controller.signal), error: null };
      } catch (error) {
        next = {
          requestKey,
          result: null,
          error: error instanceof ApiError ? error : new ApiError(FAILURE_MESSAGES.unexpected),
        };
      }
      // Aborted means a newer request replaced this one, so its outcome must not be shown.
      if (!controller.signal.aborted) setOutcome(next);
    }

    void load();
    return () => controller.abort();
  }, [query, requestKey]);

  // Loading is derived: the stored outcome belongs to an older request.
  const loading = outcome?.requestKey !== requestKey;
  return {
    result: outcome?.result ?? null,
    loading,
    error: loading ? null : outcome.error,
    retry: () => setAttempt(value => value + 1),
  };
}
