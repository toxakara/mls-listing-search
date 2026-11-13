import type { Listing } from '../model/schemas';

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

/** One search result: the listing, its score with the two parts behind it, and other feeds' copies. */
export default function ListingCard({ listing }: { listing: Listing }) {
  const otherFeeds = listing.duplicates.map(duplicate => `${duplicate.source} ${duplicate.id}`).join(', ');

  return (
    <article className="rounded border border-gray-200 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold">{listing.address}</h2>
          <p className="text-sm text-gray-500">{listing.city}, {listing.state} {listing.zip}</p>
        </div>
        <p className="text-lg font-semibold">{usd.format(listing.price)}</p>
      </div>

      <p className="mt-2 text-sm">
        {listing.bedrooms} bd · {listing.bathrooms} ba · {listing.sqft.toLocaleString('en-US')} sq ft
        {' · '}<span className="capitalize">{listing.status}</span> · listed {listing.listedDate}
      </p>
      <p className="mt-2 text-sm text-gray-700">{listing.description}</p>

      <p className="mt-3 text-sm">
        <span className="font-medium">Relevance {listing.relevanceScore.toFixed(2)} / 100</span>
        <span className="text-gray-500">
          {listing.budgetScore !== null && ` · budget fit ${listing.budgetScore.toFixed(0)}`}
          {` · recency ${listing.recencyScore.toFixed(0)}`}
        </span>
      </p>
      <p className="mt-1 text-xs text-gray-500">
        {listing.source} {listing.id}{otherFeeds && ` · also listed as ${otherFeeds}`}
      </p>
    </article>
  );
}
