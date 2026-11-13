import { act, renderHook, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { FAILURE_MESSAGES } from '../src/features/listings/api/listings';
import { useListingSearch } from '../src/features/listings/hooks/useListingSearch';
import { apiListing, jsonResponse, searchPage, validationErrorResponse } from './fakeApi';

interface PendingRequest {
  url: string;
  signal: AbortSignal | null | undefined;
  respond: (response: Response) => void;
  fail: (error: Error) => void;
}

/** Replaces fetch with one that answers only when the test says so, in any order.
 * Like a server that has already replied, it ignores aborts: dropping stale answers is the hook's job.
 */
function controlledFetch(): PendingRequest[] {
  const requests: PendingRequest[] = [];
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) =>
    new Promise<Response>((resolve, reject) => {
      requests.push({ url, signal: init?.signal, respond: resolve, fail: reject });
    }),
  );
  return requests;
}

function renderSearch(query: string) {
  return renderHook((props: { query: string }) => useListingSearch(props.query), { initialProps: { query } });
}

const reston = searchPage([apiListing({ id: 'A4', city: 'Reston', address: '22 Birch Ln' })]);
const vienna = searchPage([apiListing({ id: 'A5', city: 'Vienna', address: '55 Elm Ct' })]);

test('reports loading, then the result', async () => {
  const requests = controlledFetch();
  const { result } = renderSearch('city=Reston');
  expect(result.current).toMatchObject({ loading: true, result: null, error: null });
  expect(requests.map(request => request.url)).toEqual(['/api/listings?city=Reston']);

  requests[0].respond(jsonResponse(reston));
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current).toMatchObject({ result: reston, error: null });
});

test('keeps the previous result while the next search loads', async () => {
  const requests = controlledFetch();
  const { result, rerender } = renderSearch('city=Reston');
  requests[0].respond(jsonResponse(reston));
  await waitFor(() => expect(result.current.loading).toBe(false));

  rerender({ query: 'city=Vienna' });
  expect(result.current).toMatchObject({ loading: true, result: reston });
  requests[1].respond(jsonResponse(vienna));
  await waitFor(() => expect(result.current.result).toEqual(vienna));
});

test('drops the answer to a search that a newer one replaced', async () => {
  const requests = controlledFetch();
  const { result, rerender } = renderSearch('city=Reston');
  rerender({ query: 'city=Vienna' });
  expect(requests[0].signal?.aborted).toBe(true);

  requests[1].respond(jsonResponse(vienna));
  await waitFor(() => expect(result.current.result).toEqual(vienna));
  // The replaced search answers last, as a slow server might. One timer tick is enough for the
  // hook to read and handle that answer, which is when a missing check would put it on screen.
  await act(async () => {
    requests[0].respond(jsonResponse(reston));
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  expect(result.current).toMatchObject({ loading: false, result: vienna });
});

test('retry sends the same search again', async () => {
  const requests = controlledFetch();
  const { result } = renderSearch('city=Reston');
  const message = 'Something went wrong on our side. Please try again.';
  requests[0].respond(jsonResponse({ code: 'INTERNAL_ERROR', message, details: [] }, 500));
  await waitFor(() => expect(result.current.error?.message).toBe(message));

  act(() => result.current.retry());
  expect(result.current).toMatchObject({ loading: true, error: null });
  expect(requests.map(request => request.url)).toEqual(['/api/listings?city=Reston', '/api/listings?city=Reston']);
  requests[1].respond(jsonResponse(reston));
  await waitFor(() => expect(result.current.result).toEqual(reston));
  expect(result.current.error).toBeNull();
});

test('a rejected filter comes back as a field error rather than text', async () => {
  const requests = controlledFetch();
  const { result } = renderSearch('city=Atlantis');
  requests[0].respond(validationErrorResponse('city', 'No listings are in a city with this name'));
  await waitFor(() => expect(result.current.error).not.toBeNull());
  expect(result.current.error?.fieldErrors).toEqual({ city: 'No listings are in a city with this name' });
  expect(result.current.error?.message).toBe('');
});

test.each<[string, (request: PendingRequest) => void, string]>([
  [
    'the network fails',
    request => request.fail(new TypeError('Failed to fetch')),
    FAILURE_MESSAGES.offline,
  ],
  [
    'the backend behind the proxy is down',
    request => request.respond(new Response('Bad Gateway', { status: 502 })),
    FAILURE_MESSAGES.unavailable,
  ],
  [
    'the API cannot read the listings',
    request => request.respond(jsonResponse(
      { code: 'SERVICE_UNAVAILABLE', message: 'Listings are temporarily unavailable.', details: [] }, 503,
    )),
    'Listings are temporarily unavailable.',
  ],
  [
    'the search times out',
    request => request.fail(new DOMException('The operation timed out.', 'TimeoutError')),
    FAILURE_MESSAGES.slow,
  ],
  [
    'the body has an unexpected shape',
    request => request.respond(jsonResponse({ listings: [] })),
    FAILURE_MESSAGES.unexpected,
  ],
])('explains the failure when %s', async (_case, answer, message) => {
  const requests = controlledFetch();
  const { result } = renderSearch('');
  answer(requests[0]);
  await waitFor(() => expect(result.current.error?.message).toBe(message));
  expect(result.current.error?.fieldErrors).toEqual({});
});

test('gives up on a search that gets no answer within 10 seconds', () => {
  // jsdom's timeout signal ignores fake timers, so the test fires it by hand.
  const timeout = new AbortController();
  const timeoutSpy = vi.spyOn(AbortSignal, 'timeout').mockReturnValue(timeout.signal);
  try {
    const requests = controlledFetch();
    renderSearch('city=Reston');
    expect(timeoutSpy).toHaveBeenCalledWith(10_000);
    expect(requests[0].signal?.aborted).toBe(false);
    timeout.abort(new DOMException('The operation timed out.', 'TimeoutError'));
    expect(requests[0].signal?.aborted).toBe(true);
  } finally {
    timeoutSpy.mockRestore();
  }
});
