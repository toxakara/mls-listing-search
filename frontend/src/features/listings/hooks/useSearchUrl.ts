import { useEffect, useState } from 'react';
import { parseSearchState, toSearchParams } from '../model/filters';
import type { SearchFilters } from '../model/filters';

/** Keeps the applied search in the page URL, so it survives a reload,
 * can be shared as a link, and Back/Forward move between searches.
 */
export function useSearchUrl() {
  const [state, setState] = useState(() => parseSearchState(window.location.search));
  // Counts Back/Forward moves: the only case where the search changes without the form.
  const [historyMoves, setHistoryMoves] = useState(0);

  useEffect(() => {
    const onPopState = () => {
      setState(parseSearchState(window.location.search));
      setHistoryMoves(count => count + 1);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  function navigate(filters: SearchFilters, page: number): void {
    const search = `?${toSearchParams(filters, page)}`;
    // Submitting the same search again must not add an entry that Back would have to skip.
    if (search !== window.location.search) window.history.pushState(null, '', search);
    setState({ filters, page });
  }

  return { filters: state.filters, page: state.page, historyMoves, navigate };
}
