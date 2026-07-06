// One passenger, economy — the search page lets the user change both.
const PASSENGERS = 1;

/**
 * Build a one-way Aviasales flight-search URL for a single leg.
 *
 * Our fares come from the month-matrix source: an aggregated *cheapest price*
 * per day, not a bookable ticket. So we can't deep-link a specific fare — we
 * link to a pre-filled *search* for the leg's route and date instead. That
 * search page also lists the carriers, which is the "airline name" the user
 * wanted, without us having to carry it through the backend.
 *
 * Aviasales' path format is ORIGIN + DD + MM + DEST + passengers, e.g.
 * LON + 12 + 08 + LIS + 1 -> ".../search/LON1208LIS1". Verified live: it
 * prefills route + date and returns real flights. `flyDate` is ISO
 * `YYYY-MM-DD` (from the API / date input), already zero-padded.
 */
export function aviasalesSearchUrl(origin: string, destination: string, flyDate: string): string {
  const [, month, day] = flyDate.split("-");
  const from = origin.toUpperCase();
  const to = destination.toUpperCase();
  return `https://www.aviasales.com/search/${from}${day}${month}${to}${PASSENGERS}`;
}
