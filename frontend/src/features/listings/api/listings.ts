import { toFormErrors } from '../model/filters';
import type { FieldErrors } from '../model/filters';
import { apiErrorSchema, searchPageSchema } from '../model/schemas';
import type { SearchPage } from '../model/schemas';

/** A search gives up after this long, so a stuck backend shows a message instead of loading forever. */
const TIMEOUT_MS = 10_000;

/** What the user reads when a search can't run. Each one says what to do next. */
export const FAILURE_MESSAGES = {
  unavailable: 'Listings are temporarily unavailable. Please try again in a moment.',
  slow: 'The search is taking longer than usual. Please try again in a moment.',
  offline: "Can't connect to the listing service. Check your internet connection and try again.",
  unexpected: 'Something went wrong while loading listings. Please try again.',
} as const;

/** A failed search with text that is safe to show to the user. */
export class ApiError extends Error {
  /** Messages about filters the API rejected, keyed by form field; empty for other failures. */
  readonly fieldErrors: FieldErrors;

  constructor(message: string, fieldErrors: FieldErrors = {}) {
    super(message);
    this.fieldErrors = fieldErrors;
  }
}

/** Returns null for a body that is not JSON, e.g. the dev proxy's reply when the backend is down. */
async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/** Turns a failed response into an error, using the API's error body when there is one.
 * Messages about form fields go to `fieldErrors`; anything else becomes the message text.
 */
function toApiError(body: unknown): ApiError {
  const error = apiErrorSchema.safeParse(body);
  // A body that isn't the API's comes from the proxy in front of it: the backend is down or restarting.
  if (!error.success) return new ApiError(FAILURE_MESSAGES.unavailable);
  const { message, details } = error.data;
  if (details.length === 0) return new ApiError(message);
  const { fieldErrors, otherMessages } = toFormErrors(details);
  return new ApiError(otherMessages.join('; '), fieldErrors);
}

/** Calls GET /api/listings. `query` is the query string built by `toSearchParams`. */
export async function searchListings(query: string, signal: AbortSignal): Promise<SearchPage> {
  let response: Response;
  try {
    response = await fetch(`/api/listings?${query}`, {
      signal: AbortSignal.any([signal, AbortSignal.timeout(TIMEOUT_MS)]),
    });
  } catch (error) {
    // The caller cancelled it because a newer search replaced this one: not a failure.
    if (signal.aborted) throw error;
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new ApiError(FAILURE_MESSAGES.slow);
    }
    throw new ApiError(FAILURE_MESSAGES.offline);
  }

  const body = await readJson(response);
  if (!response.ok) throw toApiError(body);

  // The response is checked at runtime, so a backend change cannot crash a component later.
  const page = searchPageSchema.safeParse(body);
  if (!page.success) throw new ApiError(FAILURE_MESSAGES.unexpected);
  return page.data;
}
