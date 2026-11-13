import { useState } from 'react';
import {
  DEFAULT_FILTERS, LISTING_STATUSES, PAGE_SIZES, toggleStatus, validateFilters,
} from '../model/filters';
import type { FieldErrors, SearchFilters } from '../model/filters';
import Field, { errorId, inputClass } from './Field';

type TextField = 'keyword' | 'city' | 'minPrice' | 'maxPrice' | 'targetBudget';

interface SearchFormProps {
  /** The search currently shown in the results; the form starts from it. */
  applied: SearchFilters;
  /** What the API rejected in the applied search, shown next to the matching fields. */
  serverErrors: FieldErrors;
  onSearch: (filters: SearchFilters) => void;
}

/** Edits a draft of the filters. Nothing is searched until the form is submitted. */
export default function SearchForm({ applied, serverErrors, onSearch }: SearchFormProps) {
  const [draft, setDraft] = useState(applied);
  const [clientErrors, setClientErrors] = useState<FieldErrors>({});
  // A submit the form rejected never reached the API, so its errors replace the API's,
  // which are about an older search.
  const errors = Object.keys(clientErrors).length > 0 ? clientErrors : serverErrors;

  function setField<K extends keyof SearchFilters>(field: K, value: SearchFilters[K]): void {
    setDraft(previous => ({ ...previous, [field]: value }));
  }

  function submit(): void {
    const nextErrors = validateFilters(draft);
    setClientErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) onSearch(draft);
  }

  function reset(): void {
    setDraft(DEFAULT_FILTERS);
    setClientErrors({});
    onSearch(DEFAULT_FILTERS);
  }

  /** Marks a control invalid and points it at the message `Field` renders under it. */
  function invalidProps(field: keyof SearchFilters) {
    return errors[field] ? { 'aria-invalid': true, 'aria-describedby': errorId(field) } : {};
  }

  /** The five inputs differ only in these arguments.
   * Amounts are text inputs with a decimal keyboard, not type="number": a number input reports
   * a typo such as "500-000" as an empty value, so the search would silently run without it.
   */
  function textInput(field: TextField, label: string, inputMode: 'text' | 'decimal', placeholder?: string) {
    return (
      <Field label={label} htmlFor={field} error={errors[field]}>
        <input
          id={field}
          type="text"
          inputMode={inputMode}
          className={inputClass}
          placeholder={placeholder}
          value={draft[field]}
          {...invalidProps(field)}
          onChange={event => setField(field, event.target.value)}
        />
      </Field>
    );
  }

  return (
    <form className="space-y-4" noValidate onSubmit={event => { event.preventDefault(); submit(); }}>
      {textInput('keyword', 'Keyword', 'text', 'e.g. garage, pets')}
      {textInput('city', 'City', 'text', 'e.g. Springfield')}
      {textInput('minPrice', 'Min price ($)', 'decimal')}
      {textInput('maxPrice', 'Max price ($)', 'decimal')}

      <Field label="Min bedrooms" htmlFor="minBedrooms" error={errors.minBedrooms}>
        <select
          id="minBedrooms"
          className={inputClass}
          value={draft.minBedrooms}
          {...invalidProps('minBedrooms')}
          onChange={event => setField('minBedrooms', event.target.value)}
        >
          <option value="">Any</option>
          {[1, 2, 3, 4, 5].map(count => <option key={count} value={count}>{count}+</option>)}
        </select>
      </Field>

      <fieldset>
        <legend className="mb-1 text-sm font-medium">Status</legend>
        <div className="flex gap-4">
          {LISTING_STATUSES.map(status => (
            <label key={status} className="flex items-center gap-1 text-sm capitalize">
              <input
                type="checkbox"
                checked={draft.statuses.includes(status)}
                onChange={() => setField('statuses', toggleStatus(draft.statuses, status))}
              />
              {status}
            </label>
          ))}
        </div>
        {errors.statuses && <p className="mt-1 text-sm text-red-600">{errors.statuses}</p>}
      </fieldset>

      {textInput('targetBudget', 'Target budget ($)', 'decimal', 'Optional')}
      <p className="text-xs text-gray-500">
        With a budget, closeness to it counts for 70% of the score and recency for 30%. Without one,
        the newest listings come first.
      </p>

      <Field label="Results per page" htmlFor="pageSize" error={errors.pageSize}>
        <select
          id="pageSize"
          className={inputClass}
          value={draft.pageSize}
          {...invalidProps('pageSize')}
          onChange={event => setField('pageSize', Number(event.target.value))}
        >
          {PAGE_SIZES.map(size => <option key={size} value={size}>{size}</option>)}
        </select>
      </Field>

      <div className="flex gap-2">
        <button type="submit" className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          Search
        </button>
        <button type="button" className="rounded border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50" onClick={reset}>
          Reset
        </button>
      </div>
    </form>
  );
}
