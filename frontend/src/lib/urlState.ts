export type CityInput = { iata: string; days: number };
export type TripInput = {
  origin_airport: string;
  return_airport: string;
  cities: CityInput[];
  start_date: string;
  flex_days: number;
};

// URL shape: ?from=LIS&to=BER&cities=BCN:3,ROM:2&start=2026-07-01&flex=3
export function encodeTrip(trip: TripInput): string {
  const params = new URLSearchParams({
    from: trip.origin_airport,
    to: trip.return_airport,
    cities: trip.cities.map((c) => `${c.iata}:${c.days}`).join(","),
    start: trip.start_date,
    flex: String(trip.flex_days),
  });
  return `?${params.toString()}`;
}

export function decodeTrip(search: string): TripInput | null {
  const p = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const from = p.get("from");
  const to = p.get("to");
  const citiesRaw = p.get("cities");
  const start = p.get("start");
  const flexRaw = p.get("flex");
  if (!from || !to || !citiesRaw || !start || flexRaw === null) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start)) return null;
  const flex = Number(flexRaw);
  if (!Number.isInteger(flex) || flex < 0 || flex > 7) return null;

  const cities: CityInput[] = [];
  for (const token of citiesRaw.split(",")) {
    const [iata, daysRaw] = token.split(":");
    const days = Number(daysRaw);
    if (!iata || iata.length !== 3 || !Number.isInteger(days) || days <= 0) return null;
    cities.push({ iata, days });
  }
  if (cities.length < 1 || cities.length > 8) return null;
  return { origin_airport: from, return_airport: to, cities, start_date: start, flex_days: flex };
}

// Adapter to the API request shape.
export function toApiRequest(trip: TripInput) {
  return {
    origin_airport: trip.origin_airport,
    return_airport: trip.return_airport,
    cities: trip.cities.map((c) => c.iata),
    days_per_city: Object.fromEntries(trip.cities.map((c) => [c.iata, c.days])),
    start_date: trip.start_date,
    flex_days: trip.flex_days,
  };
}
