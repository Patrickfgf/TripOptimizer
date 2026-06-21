import { describe, it, expect } from "vitest";
import { encodeTrip, decodeTrip, type TripInput } from "./urlState";

const TRIP: TripInput = {
  origin_airport: "LIS",
  return_airport: "BER",
  cities: [{ iata: "BCN", days: 3 }, { iata: "ROM", days: 2 }],
  start_date: "2026-07-01",
  flex_days: 3,
};

describe("urlState", () => {
  it("round-trips a valid trip", () => {
    const decoded = decodeTrip(encodeTrip(TRIP));
    expect(decoded).toEqual(TRIP);
  });
  it("returns null for junk", () => {
    expect(decodeTrip("?from=LIS")).toBeNull();
  });
  it("returns null for empty search", () => {
    expect(decodeTrip("")).toBeNull();
  });
});
