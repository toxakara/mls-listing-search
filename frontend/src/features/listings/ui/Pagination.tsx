interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const buttonClass = 'rounded border border-gray-300 px-3 py-1 hover:bg-gray-50 disabled:opacity-40';

/** Previous / Next with the current position; the buttons are disabled at the ends. */
export default function Pagination({ page, totalPages, onPageChange }: PaginationProps) {
  return (
    <nav aria-label="Pagination" className="mt-4 flex items-center gap-3 text-sm">
      <button type="button" className={buttonClass} disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        Previous
      </button>
      <span>Page {page} of {totalPages}</span>
      <button type="button" className={buttonClass} disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
        Next
      </button>
    </nav>
  );
}
