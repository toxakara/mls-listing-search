import { z } from 'zod';
import { LISTING_STATUSES } from './filters';

/** Shape of a successful GET /api/listings response; the TypeScript types are inferred from it. */
const listingSchema = z.object({
  id: z.string(),
  source: z.string(),
  address: z.string(),
  city: z.string(),
  state: z.string(),
  zip: z.string(),
  price: z.number(),
  bedrooms: z.number(),
  bathrooms: z.number(),
  sqft: z.number(),
  listedDate: z.iso.date(),
  status: z.enum(LISTING_STATUSES),
  description: z.string(),
  relevanceScore: z.number(),
  recencyScore: z.number(),
  // null when the search has no target budget
  budgetScore: z.number().nullable(),
  // the same property as reported by other feeds
  duplicates: z.array(z.object({ source: z.string(), id: z.string() })),
});

export const searchPageSchema = z.object({
  items: z.array(listingSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
});

/** Body of every failed response, whatever the status. */
export const apiErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  // one entry per invalid query parameter; empty for other errors
  details: z.array(z.object({ field: z.string().nullable(), message: z.string() })),
});

export type Listing = z.infer<typeof listingSchema>;
export type SearchPage = z.infer<typeof searchPageSchema>;
