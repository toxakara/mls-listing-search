// Pure functions of the search form model: validation, the URL round trip, API error mapping.
import { expect, test } from 'vitest';
import {
  DEFAULT_FILTERS, parseSearchState, toFormErrors, toSearchParams, toggleStatus, validateFilters,
} from '../src/features/listings/model/filters';
import type { SearchFilters } from '../src/features/listings/model/filters';

test('default filters are valid', () => {
  expect(validateFilters(DEFAULT_FILTERS)).toEqual({});
});

test('min price above max price is reported on maxPrice', () => {
  const errors = validateFilters({ ...DEFAULT_FILTERS, minPrice: '500000', maxPrice: '200000' });
  expect(Object.keys(errors)).toEqual(['maxPrice']);
});

test('equal min and max price, and zero, are valid', () => {
  expect(validateFilters({ ...DEFAULT_FILTERS, minPrice: '0', maxPrice: '0' })).toEqual({});
});

test('each invalid field gets its own message', () => {
  const errors = validateFilters({
    ...DEFAULT_FILTERS, minPrice: '-1', maxPrice: 'abc', targetBudget: '0', statuses: [],
  });
  expect(errors.minPrice).toMatch(/negative/);
  expect(errors.maxPrice).toMatch(/number/);
  expect(errors.targetBudget).toMatch(/greater than zero/);
  expect(errors.statuses).toMatch(/at least one/);
});

test('with no filters at all, the form is valid and the query has only defaults', () => {
  expect(toSearchParams(DEFAULT_FILTERS, 1).toString()).toBe('status=active&page=1&pageSize=6');
});

test('every filter filled in with valid values is valid', () => {
  const filters: SearchFilters = {
    keyword: 'pet garage', city: 'Springfield', minPrice: '400000', maxPrice: '460000.50',
    minBedrooms: '2', targetBudget: '450000', statuses: ['active', 'pending', 'sold'], pageSize: 24,
  };
  expect(validateFilters(filters)).toEqual({});
  expect(parseSearchState(`?${toSearchParams(filters, 1).toString()}`)).toEqual({ filters, page: 1 });
});

for (const value of ['-1', '-0.01', '-450000']) {
  test(`negative amount ${value} is rejected in every amount field`, () => {
    const errors = validateFilters({ ...DEFAULT_FILTERS, minPrice: value, maxPrice: value, targetBudget: value });
    expect(Object.keys(errors)).toEqual(['minPrice', 'maxPrice', 'targetBudget']);
  });
}

for (const value of ['abc', '1,000', '$500', 'Infinity', '1e999', 'NaN']) {
  test(`"${value}" is not accepted as an amount`, () => {
    const errors = validateFilters({ ...DEFAULT_FILTERS, minPrice: value, targetBudget: value });
    expect(errors.minPrice).toMatch(/must be a number/);
    expect(errors.targetBudget).toMatch(/must be a number/);
  });
}

test('blank and padded amounts are treated as typed', () => {
  expect(validateFilters({ ...DEFAULT_FILTERS, minPrice: '   ', maxPrice: ' 500000 ' })).toEqual({});
  expect(toSearchParams({ ...DEFAULT_FILTERS, minPrice: '   ', maxPrice: ' 500000 ' }, 1).get('maxPrice')).toBe('500000');
});

test('prices are compared as numbers, not as text', () => {
  // As strings "90000" > "100000"; as numbers it is a valid range.
  expect(validateFilters({ ...DEFAULT_FILTERS, minPrice: '90000', maxPrice: '100000' })).toEqual({});
});

test('only one price bound is fine', () => {
  expect(validateFilters({ ...DEFAULT_FILTERS, minPrice: '500000' })).toEqual({});
  expect(validateFilters({ ...DEFAULT_FILTERS, maxPrice: '500000' })).toEqual({});
});

test('a price range error is not added on top of an invalid price', () => {
  const errors = validateFilters({ ...DEFAULT_FILTERS, minPrice: '-5', maxPrice: '-10' });
  expect(errors.maxPrice).toMatch(/negative/);
});

for (const query of ['?page=0', '?page=-3', '?page=1.5', '?page=abc', '?page=', '?page=1e400', '?page=1e60']) {
  test(`URL ${query} opens the first page`, () => {
    expect(parseSearchState(query).page).toBe(1);
  });
}

for (const query of ['?pageSize=0', '?pageSize=-6', '?pageSize=5', '?pageSize=1000', '?pageSize=abc']) {
  test(`URL ${query} uses the default page size`, () => {
    expect(parseSearchState(query).filters.pageSize).toBe(DEFAULT_FILTERS.pageSize);
  });
}

test('URL statuses: unknown ones are dropped, repeats and order are normalised', () => {
  expect(parseSearchState('?status=sold&status=gone&status=active&status=sold').filters.statuses).toEqual(['active', 'sold']);
  expect(parseSearchState('?status=ACTIVE').filters.statuses).toEqual(DEFAULT_FILTERS.statuses);
});

test('unknown URL parameters are ignored', () => {
  expect(parseSearchState('?utm_source=mail&foo=1')).toEqual({ filters: DEFAULT_FILTERS, page: 1 });
});

test('toggleStatus adds and removes a status in a fixed order', () => {
  expect(toggleStatus(['sold'], 'active')).toEqual(['active', 'sold']);
  expect(toggleStatus(['active', 'sold'], 'active')).toEqual(['sold']);
});

test('query string omits empty filters and repeats status', () => {
  const query = toSearchParams({ ...DEFAULT_FILTERS, city: ' New York ', statuses: ['active', 'pending'] }, 2);
  expect(query.toString()).toBe('city=New+York&status=active&status=pending&page=2&pageSize=6');
});

test('filters survive a round trip through the URL', () => {
  const filters: SearchFilters = {
    ...DEFAULT_FILTERS, city: 'Reston', minPrice: '400000', targetBudget: '500000',
    statuses: ['active', 'sold'], pageSize: 12,
  };
  expect(parseSearchState(`?${toSearchParams(filters, 3).toString()}`)).toEqual({ filters, page: 3 });
});

test('an empty URL is the default search', () => {
  expect(parseSearchState('')).toEqual({ filters: DEFAULT_FILTERS, page: 1 });
});

test('unusable page, page size and status in the URL fall back to defaults', () => {
  const { filters, page } = parseSearchState('?page=-2&pageSize=999&status=archived&minPrice=abc');
  expect(page).toBe(1);
  expect(filters.pageSize).toBe(DEFAULT_FILTERS.pageSize);
  expect(filters.statuses).toEqual(DEFAULT_FILTERS.statuses);
  // Text values are passed through so the API can report them.
  expect(filters.minPrice).toBe('abc');
});

test('API errors on query parameters go to the matching form fields', () => {
  const { fieldErrors, otherMessages } = toFormErrors([
    { field: 'city', message: 'No listings are in a city with this name' },
    { field: 'minBedrooms', message: 'Input should be a valid integer' },
    { field: 'status', message: 'Input should be active, pending or sold' },
    { field: 'pageSize', message: 'Input should be at most 100' },
  ]);
  expect(fieldErrors).toEqual({
    city: 'No listings are in a city with this name',
    minBedrooms: 'Input should be a valid integer',
    statuses: 'Input should be active, pending or sold',
    pageSize: 'Input should be at most 100',
  });
  expect(otherMessages).toEqual([]);
});

test('API errors without a form field stay as text', () => {
  const { fieldErrors, otherMessages } = toFormErrors([
    { field: 'page', message: 'Input should be at least 1' },
    { field: 'minprice', message: 'Extra inputs are not permitted' },
    { field: null, message: 'Invalid request' },
  ]);
  expect(fieldErrors).toEqual({});
  expect(otherMessages).toEqual([
    'page: Input should be at least 1',
    'minprice: Extra inputs are not permitted',
    'Invalid request',
  ]);
});
