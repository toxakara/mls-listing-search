import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { DEFAULT_FILTERS } from '../src/features/listings/model/filters';
import type { FieldErrors } from '../src/features/listings/model/filters';
import SearchForm from '../src/features/listings/ui/SearchForm';

const CITY_ERROR = 'No listings are in a city with this name';

function renderForm(serverErrors: FieldErrors = {}) {
  const onSearch = vi.fn();
  render(<SearchForm applied={DEFAULT_FILTERS} serverErrors={serverErrors} onSearch={onSearch} />);
  return { onSearch, user: userEvent.setup() };
}

test('a mistyped amount is reported instead of being dropped from the search', async () => {
  const { onSearch, user } = renderForm();
  await user.type(screen.getByLabelText('Min price ($)'), '500-000');
  await user.click(screen.getByRole('button', { name: 'Search' }));

  screen.getByText('Minimum price must be a number.');
  expect(screen.getByLabelText('Min price ($)').getAttribute('aria-invalid')).toBe('true');
  expect(onSearch).not.toHaveBeenCalled();
});

test('a valid form searches with what was entered', async () => {
  const { onSearch, user } = renderForm();
  await user.type(screen.getByLabelText('City'), 'Reston');
  await user.type(screen.getByLabelText('Min price ($)'), '400000');
  await user.selectOptions(screen.getByLabelText('Min bedrooms'), '3');
  await user.click(screen.getByRole('checkbox', { name: 'pending' }));
  await user.keyboard('{Enter}');

  expect(onSearch).toHaveBeenCalledWith({
    ...DEFAULT_FILTERS,
    city: 'Reston',
    minPrice: '400000',
    minBedrooms: '3',
    statuses: ['active', 'pending'],
  });
});

test('errors from the API appear on their fields', () => {
  renderForm({ city: CITY_ERROR, minBedrooms: 'Input should be a valid integer' });

  const city = screen.getByLabelText('City');
  expect(city.getAttribute('aria-invalid')).toBe('true');
  expect(document.getElementById(city.getAttribute('aria-describedby') ?? '')?.textContent).toBe(CITY_ERROR);
  expect(screen.getByLabelText('Min bedrooms').getAttribute('aria-invalid')).toBe('true');
  screen.getByText('Input should be a valid integer');
});

test("the form's own errors replace the API's, which are about an older search", async () => {
  const { user } = renderForm({ city: CITY_ERROR });
  await user.type(screen.getByLabelText('Min price ($)'), '-5');
  await user.click(screen.getByRole('button', { name: 'Search' }));

  screen.getByText('Minimum price cannot be negative.');
  expect(screen.queryByText(CITY_ERROR)).toBeNull();
});

test('Reset clears the form and searches with the defaults', async () => {
  const { onSearch, user } = renderForm();
  await user.type(screen.getByLabelText('City'), 'Reston');
  await user.click(screen.getByRole('button', { name: 'Reset' }));

  expect(screen.getByLabelText('City')).toHaveProperty('value', '');
  expect(onSearch).toHaveBeenCalledWith(DEFAULT_FILTERS);
});
