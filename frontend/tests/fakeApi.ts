/** Response bodies in the shape the real API sends, for tests that replace `fetch`. */
import type { Listing, SearchPage } from '../src/features/listings/model/schemas';

export function apiListing(overrides: Partial<Listing> = {}): Listing {
  return {
    id: 'A1',
    source: 'MLS_A',
    address: '123 Main St, Apt 4B',
    city: 'Springfield',
    state: 'VA',
    zip: '22150',
    price: 450000,
    bedrooms: 2,
    bathrooms: 1.5,
    sqft: 980,
    listedDate: '2026-08-29',
    status: 'active',
    description: 'Bright top-floor condo. Pet friendly.',
    relevanceScore: 42.5,
    recencyScore: 42.5,
    budgetScore: null,
    duplicates: [],
    ...overrides,
  };
}

export function searchPage(items: Listing[], pagination: Partial<SearchPage['pagination']> = {}): SearchPage {
  const total = pagination.total ?? items.length;
  return {
    items,
    pagination: { page: 1, pageSize: 6, total, totalPages: Math.ceil(total / 6), ...pagination },
  };
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

/** The 422 the API sends for one rejected query parameter. */
export function validationErrorResponse(field: string, message: string): Response {
  return jsonResponse(
    { code: 'VALIDATION_ERROR', message: 'Invalid search parameters', details: [{ field, message }] },
    422,
  );
}
