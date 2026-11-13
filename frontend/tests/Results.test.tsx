import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { ApiError, FAILURE_MESSAGES } from '../src/features/listings/api/listings';
import type { SearchPage } from '../src/features/listings/model/schemas';
import Results from '../src/features/listings/ui/Results';
import { apiListing, searchPage } from './fakeApi';

interface State {
  result?: SearchPage | null;
  loading?: boolean;
  error?: ApiError | null;
}

function renderResults({ result = null, loading = false, error = null }: State) {
  const onPageChange = vi.fn();
  const onRetry = vi.fn();
  render(
    <Results result={result} loading={loading} error={error} onPageChange={onPageChange} onRetry={onRetry} />,
  );
  return { onPageChange, onRetry, user: userEvent.setup() };
}

const twoPages = searchPage(
  [
    apiListing({ id: 'A1', address: '123 Main St, Apt 4B', price: 450000, bedrooms: 2, relevanceScore: 82.89 }),
    apiListing({ id: 'A5', address: '55 Elm Ct', price: 470000, bedrooms: 3, relevanceScore: 80.83 }),
  ],
  { page: 1, pageSize: 2, total: 3, totalPages: 2 },
);

test('shows a loading message before the first result', () => {
  renderResults({ loading: true });
  screen.getByText('Loading listings…');
});

test('shows loading, not "no results", while a new search replaces an empty one', () => {
  renderResults({ result: searchPage([]), loading: true });
  screen.getByText('Loading listings…');
  expect(screen.queryByText('No listings match these filters.')).toBeNull();
});

test('says so when nothing matches', () => {
  renderResults({ result: searchPage([]) });
  screen.getByText('No listings match these filters.');
});

test('offers the first page when the page is past the end', async () => {
  const { onPageChange, user } = renderResults({ result: searchPage([], { page: 5, total: 7, totalPages: 2 }) });
  screen.getByText('Page 5 is past the last page (2).');
  await user.click(screen.getByRole('button', { name: 'Go to the first page' }));
  expect(onPageChange).toHaveBeenCalledWith(1);
});

test('shows each listing with its price, bedrooms and score, and moves between pages', async () => {
  const { onPageChange, user } = renderResults({ result: twoPages });
  screen.getByText('3 properties, ranked by relevance');
  const [first, second] = screen.getAllByRole('article');
  expect(first.textContent).toContain('123 Main St, Apt 4B');
  expect(first.textContent).toContain('$450,000');
  expect(first.textContent).toContain('2 bd');
  expect(first.textContent).toContain('Relevance 82.89 / 100');
  expect(second.textContent).toContain('55 Elm Ct');

  screen.getByText('Page 1 of 2');
  expect(screen.getByRole('button', { name: 'Previous' })).toHaveProperty('disabled', true);
  await user.click(screen.getByRole('button', { name: 'Next' }));
  expect(onPageChange).toHaveBeenCalledWith(2);
});

test('keeps the current page on screen, marked busy, while the next one loads', () => {
  renderResults({ result: twoPages, loading: true });
  screen.getByText(/updating…/);
  const articles = screen.getAllByRole('article');
  expect(articles).toHaveLength(2);
  expect(articles[0].closest('section')?.getAttribute('aria-busy')).toBe('true');
});

test('a rejected filter points at the form and offers no retry', () => {
  renderResults({ error: new ApiError('', { city: 'No listings are in a city with this name' }) });
  expect(screen.getByRole('alert').textContent).toBe('Check the highlighted filters');
  expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
});

test('any other failure shows its message and can be retried', async () => {
  const { onRetry, user } = renderResults({ error: new ApiError(FAILURE_MESSAGES.unavailable) });
  screen.getByText(FAILURE_MESSAGES.unavailable);
  await user.click(screen.getByRole('button', { name: 'Try again' }));
  expect(onRetry).toHaveBeenCalledOnce();
});
