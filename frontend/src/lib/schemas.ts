import { z } from "zod";

export const AirportSchema = z.object({
  iata: z.string(),
  name: z.string(),
  city: z.string(),
  country: z.string(),
  lat: z.number(),
  lon: z.number(),
});
export type Airport = z.infer<typeof AirportSchema>;

export const LegSchema = z.object({
  origin: z.string(),
  destination: z.string(),
  fly_date: z.string(),
  price: z.number(),
  source: z.string(),
});
export type Leg = z.infer<typeof LegSchema>;

export const ItinerarySchema = z.object({
  order: z.array(z.string()),
  start_offset: z.number(),
  legs: z.array(LegSchema),
  total: z.number(),
});
export type Itinerary = z.infer<typeof ItinerarySchema>;

// A full result: every leg is priced from real data (`cached`; `mixed` if sources differ).
export const TripResultSchema = z.object({
  status: z.literal("ok"),
  best: ItinerarySchema,
  alternatives: z.array(ItinerarySchema),
  data_source: z.enum(["cached", "mixed"]),
  snapshot_date: z.string().nullable(),
});
export type TripResult = z.infer<typeof TripResultSchema>;

// No fully-real itinerary exists: these (origin, destination) pairs had no real fare in
// the window. Shown honestly instead of a fabricated price (real-or-nothing).
export const IncompleteTripSchema = z.object({
  status: z.literal("incomplete"),
  missing_routes: z.array(z.tuple([z.string(), z.string()])),
  snapshot_date: z.string().nullable(),
});
export type IncompleteTrip = z.infer<typeof IncompleteTripSchema>;

// The /optimize response is one of the two shapes, discriminated by `status`.
export const OptimizeResponseSchema = z.discriminatedUnion("status", [
  TripResultSchema,
  IncompleteTripSchema,
]);
export type OptimizeResponse = z.infer<typeof OptimizeResponseSchema>;

// Client-side request model. Mirrors the backend guardrails so requests are valid before sending.
export const TripRequestSchema = z
  .object({
    origin_airport: z.string().length(3),
    return_airport: z.string().length(3),
    cities: z.array(z.string().length(3)).min(1).max(8),
    days_per_city: z.record(z.string(), z.number().int().positive()),
    start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    flex_days: z.number().int().min(0).max(7),
  })
  .refine((r) => r.cities.every((c) => r.days_per_city[c] > 0), {
    message: "Every city needs days > 0",
    path: ["days_per_city"],
  });
export type TripRequest = z.infer<typeof TripRequestSchema>;
