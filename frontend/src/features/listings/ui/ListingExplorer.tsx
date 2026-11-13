import { toSearchParams } from '../model/filters';
import { useListingSearch } from '../hooks/useListingSearch';
import { useSearchUrl } from '../hooks/useSearchUrl';
import Results from './Results';
import SearchForm from './SearchForm';

export default function ListingExplorer() {
  const { filters, page, historyMoves, navigate } = useSearchUrl();
  const { result, loading, error, retry } = useListingSearch(toSearchParams(filters, page).toString());

  return (
    <div className="grid items-start gap-8 md:grid-cols-[18rem_1fr]">
      {/* The form keeps its own draft. After Back/Forward the key changes, which remounts
          the form so its inputs show the search that is now on screen. */}
      <SearchForm
        key={historyMoves}
        applied={filters}
        serverErrors={error?.fieldErrors ?? {}}
        onSearch={next => navigate(next, 1)}
      />
      <Results
        result={result}
        loading={loading}
        error={error}
        onPageChange={next => navigate(filters, next)}
        onRetry={retry}
      />
    </div>
  );
}
