import type { ApiError } from '../api/listings';
import type { SearchPage } from '../model/schemas';
import ListingCard from './ListingCard';
import Pagination from './Pagination';

interface ResultsProps {
  result: SearchPage | null;
  loading: boolean;
  error: ApiError | null;
  onPageChange: (page: number) => void;
  onRetry: () => void;
}

/** Shows exactly one of: error, loading, no results, or the current page of listings. */
export default function Results({ result, loading, error, onPageChange, onRetry }: ResultsProps) {
  if (error) {
    // Rejected filters are shown on the form; sending the same search again cannot help.
    const aboutFilters = Object.keys(error.fieldErrors).length > 0;
    return (
      <div role="alert" className="rounded border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        <p className="font-medium">{aboutFilters ? 'Check the highlighted filters' : 'Could not load listings'}</p>
        {error.message && <p className="mt-1">{error.message}</p>}
        {!aboutFilters && (
          <button type="button" className="mt-3 rounded border border-red-300 bg-white px-3 py-1" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    );
  }

  // A previous page of listings stays on screen while the next loads; an empty one would say
  // "no results" about a search that has not finished.
  if (!result || (loading && result.items.length === 0)) {
    return <p className="text-sm text-gray-500">Loading listings…</p>;
  }

  const { page, total, totalPages } = result.pagination;

  if (total === 0) {
    return <p className="text-sm text-gray-500">No listings match these filters.</p>;
  }

  if (result.items.length === 0) {
    return (
      <div className="text-sm text-gray-500">
        <p>Page {page} is past the last page ({totalPages}).</p>
        <button type="button" className="mt-2 text-blue-600 underline" onClick={() => onPageChange(1)}>
          Go to the first page
        </button>
      </div>
    );
  }

  return (
    <section aria-busy={loading}>
      <p className="mb-3 text-sm text-gray-500">
        {total} {total === 1 ? 'property' : 'properties'}, ranked by relevance{loading && ' · updating…'}
      </p>
      {/* The previous page stays visible, dimmed, until the next one arrives. */}
      <ul className={`space-y-3 ${loading ? 'opacity-50' : ''}`}>
        {result.items.map(listing => (
          <li key={`${listing.source}:${listing.id}`}><ListingCard listing={listing} /></li>
        ))}
      </ul>
      <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />
    </section>
  );
}
