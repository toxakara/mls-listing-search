import ListingExplorer from './features/listings/ui/ListingExplorer';

export default function App() {
  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="mb-6 text-2xl font-semibold">MLS Listing Search</h1>
      <ListingExplorer />
    </main>
  );
}
