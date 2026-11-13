import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';
import ListingExplorer from '../src/features/listings/ui/ListingExplorer';
import { apiListing, jsonResponse, searchPage, validationErrorResponse } from './fakeApi';

const CITY_ERROR = 'No listings are in a city with this name';
const springfield = [1, 2, 3, 4, 5].map(n => apiListing({ id: `A${n}`, address: `${n} Oak St` }));
const reston = apiListing({ id: 'B1', city: 'Reston', address: '22 Birch Ln' });

/** Stands in for the API: Springfield or Reston listings by city, paged, and a 422 for Atlantis. */
function fakeApi() {
  const fetch = vi.fn((url: string) => {
    const params = new URL(url, window.location.origin).searchParams;
    const city = params.get('city');
    if (city === 'Atlantis') return Promise.resolve(validationErrorResponse('city', CITY_ERROR));
    const matches = city === 'Reston' ? [reston] : springfield;
    const page = Number(params.get('page'));
    const pageSize = Number(params.get('pageSize'));
    const items = matches.slice((page - 1) * pageSize, page * pageSize);
    const pagination = { page, pageSize, total: matches.length, totalPages: Math.ceil(matches.length / pageSize) };
    return Promise.resolve(jsonResponse(searchPage(items, pagination)));
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

function renderExplorer() {
  const fetch = fakeApi();
  render(<ListingExplorer />);
  return { fetch, user: userEvent.setup() };
}

beforeEach(() => {
  window.history.replaceState(null, '', '/');
});

test('searching and paging keep the search in the URL and show the matching page', async () => {
  const { fetch, user } = renderExplorer();
  await screen.findByText('1 Oak St');

  await user.selectOptions(screen.getByLabelText('Results per page'), '4');
  await user.click(screen.getByRole('button', { name: 'Search' }));
  await screen.findByText('Page 1 of 2');
  expect(window.location.search).toBe('?status=active&page=1&pageSize=4');

  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('5 Oak St');
  expect(window.location.search).toBe('?status=active&page=2&pageSize=4');
  expect(fetch).toHaveBeenLastCalledWith('/api/listings?status=active&page=2&pageSize=4', expect.anything());
});

test('an unknown city is highlighted on the form until it is fixed', async () => {
  const { user } = renderExplorer();
  const city = screen.getByLabelText('City');
  await user.type(city, 'Atlantis');
  await user.click(screen.getByRole('button', { name: 'Search' }));

  await screen.findByText(CITY_ERROR);
  expect(city.getAttribute('aria-invalid')).toBe('true');
  expect(screen.getByRole('alert').textContent).toBe('Check the highlighted filters');

  await user.clear(city);
  await user.type(city, 'Reston');
  await user.click(screen.getByRole('button', { name: 'Search' }));
  await screen.findByText('22 Birch Ln');
  expect(screen.queryByText(CITY_ERROR)).toBeNull();
  expect(city.getAttribute('aria-invalid')).toBeNull();
});

test('Back brings the previous search back into the form and the results', async () => {
  const { user } = renderExplorer();
  await screen.findByText('1 Oak St');
  await user.type(screen.getByLabelText('City'), 'Reston');
  await user.click(screen.getByRole('button', { name: 'Search' }));
  await screen.findByText('22 Birch Ln');

  act(() => window.history.back());
  await screen.findByText('1 Oak St');
  expect(window.location.search).toBe('');
  expect(screen.getByLabelText('City')).toHaveProperty('value', '');
  expect(screen.queryByText('22 Birch Ln')).toBeNull();
});
