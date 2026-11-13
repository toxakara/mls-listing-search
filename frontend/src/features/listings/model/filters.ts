/** Search form state: defaults, validation, and conversion to and from the query string. */

export const LISTING_STATUSES = ['active', 'pending', 'sold'] as const;
export type ListingStatus = (typeof LISTING_STATUSES)[number];

export const PAGE_SIZES = [4, 6, 12, 24] as const;

/** Numeric inputs are kept as strings, exactly as typed; the API parses them. */
export interface SearchFilters {
  keyword: string;
  city: string;
  minPrice: string;
  maxPrice: string;
  minBedrooms: string;
  targetBudget: string;
  statuses: readonly ListingStatus[];
  pageSize: number;
}

/** One message per form field; an empty object means the form is valid. */
export type FieldErrors = Partial<Record<keyof SearchFilters, string>>;

/** Same defaults as the API, so an empty URL and an empty request are the same search. */
export const DEFAULT_FILTERS: SearchFilters = {
  keyword: '',
  city: '',
  minPrice: '',
  maxPrice: '',
  minBedrooms: '',
  targetBudget: '',
  statuses: ['active'],
  pageSize: 6,
};

const TEXT_FIELDS = ['keyword', 'city', 'minPrice', 'maxPrice', 'minBedrooms', 'targetBudget'] as const;

const AMOUNT_FIELDS = [
  ['minPrice', 'Minimum price'],
  ['maxPrice', 'Maximum price'],
  ['targetBudget', 'Target budget'],
] as const;

function amountError(label: string, raw: string): string | undefined {
  if (raw.trim() === '') return undefined;
  const amount = Number(raw);
  if (!Number.isFinite(amount)) return `${label} must be a number.`;
  if (amount < 0) return `${label} cannot be negative.`;
  return undefined;
}

/** Catches mistakes before a request is sent. The API validates again and stays authoritative. */
export function validateFilters(filters: SearchFilters): FieldErrors {
  const errors: FieldErrors = {};
  for (const [field, label] of AMOUNT_FIELDS) {
    const error = amountError(label, filters[field]);
    if (error) errors[field] = error;
  }
  if (!errors.targetBudget && filters.targetBudget.trim() !== '' && Number(filters.targetBudget) === 0) {
    errors.targetBudget = 'Target budget must be greater than zero.';
  }
  const bothPricesValid = !errors.minPrice && !errors.maxPrice
    && filters.minPrice.trim() !== '' && filters.maxPrice.trim() !== '';
  if (bothPricesValid && Number(filters.minPrice) > Number(filters.maxPrice)) {
    errors.maxPrice = 'Maximum price must be at least the minimum price.';
  }
  if (filters.statuses.length === 0) errors.statuses = 'Select at least one status.';
  return errors;
}

/** Sorts the API's validation messages into the form fields they belong to and the rest.
 * The API names query parameters (`field` is null for the request as a whole); `page` and unknown
 * parameters have no form field, so their messages stay text.
 */
export function toFormErrors(
  details: readonly { field: string | null; message: string }[],
): { fieldErrors: FieldErrors; otherMessages: string[] } {
  const fieldErrors: FieldErrors = {};
  const otherMessages: string[] = [];
  for (const { field, message } of details) {
    const formField = field === null ? undefined : formFieldFor(field);
    if (formField) fieldErrors[formField] = message;
    else otherMessages.push(field === null ? message : `${field}: ${message}`);
  }
  return { fieldErrors, otherMessages };
}

/** Query parameters are named like the form fields, except the repeatable `status`. */
function formFieldFor(param: string): keyof SearchFilters | undefined {
  if (param === 'status') return 'statuses';
  if (param === 'pageSize') return 'pageSize';
  return TEXT_FIELDS.find(field => field === param);
}

/** Add or remove one status, keeping the fixed active/pending/sold order. */
export function toggleStatus(statuses: readonly ListingStatus[], status: ListingStatus): ListingStatus[] {
  const selected = statuses.includes(status)
    ? statuses.filter(value => value !== status)
    : [...statuses, status];
  return LISTING_STATUSES.filter(value => selected.includes(value));
}

/** Builds the query string. The API request and the page URL use the same parameter names. */
export function toSearchParams(filters: SearchFilters, page: number): URLSearchParams {
  const params = new URLSearchParams();
  for (const field of TEXT_FIELDS) {
    const value = filters[field].trim();
    if (value !== '') params.set(field, value);
  }
  for (const status of filters.statuses) params.append('status', status);
  params.set('page', String(page));
  params.set('pageSize', String(filters.pageSize));
  return params;
}

/** Reads the search from the page URL.
 * Text values are kept as they are, so the API reports a hand-edited `minPrice=abc`.
 * Statuses, page size and page fall back to defaults when the URL has no usable value.
 */
export function parseSearchState(search: string): { filters: SearchFilters; page: number } {
  const params = new URLSearchParams(search);
  const filters = { ...DEFAULT_FILTERS };
  for (const field of TEXT_FIELDS) filters[field] = params.get(field) ?? '';

  const statuses = LISTING_STATUSES.filter(status => params.getAll('status').includes(status));
  if (statuses.length > 0) filters.statuses = statuses;

  const pageSize = PAGE_SIZES.find(size => String(size) === params.get('pageSize'));
  if (pageSize) filters.pageSize = pageSize;

  // A safe integer, so `1e60` doesn't reach the API as "1e+60", which it can't parse as a page.
  const page = Number(params.get('page'));
  return { filters, page: Number.isSafeInteger(page) && page >= 1 ? page : 1 };
}
