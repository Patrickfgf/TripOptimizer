import { describe, it, expect } from "vitest";
import { AirportSchema, TripResultSchema } from "./schemas";

describe("AirportSchema", () => {
  it("parses a valid airport", () => {
    const a = AirportSchema.parse({ iata: "LIS", name: "Lisbon", city: "Lisbon", country: "PT", lat: 38.7, lon: -9.1 });
    expect(a.iata).toBe("LIS");
  });
  it("rejects a missing field", () => {
    expect(() => AirportSchema.parse({ iata: "LIS" })).toThrow();
  });
});

describe("TripResultSchema", () => {
  it("parses a full result", () => {
    const r = TripResultSchema.parse({
      best: { order: ["BCN"], start_offset: 0, total: 48, legs: [
        { origin: "LIS", destination: "BCN", fly_date: "2026-07-01", price: 48, source: "cached" },
      ] },
      alternatives: [],
      data_source: "cached",
      snapshot_date: "2026-06-15",
    });
    expect(r.best.total).toBe(48);
    expect(r.data_source).toBe("cached");
  });
  it("accepts null snapshot_date", () => {
    const r = TripResultSchema.parse({
      best: { order: [], start_offset: 0, total: 0, legs: [] },
      alternatives: [], data_source: "synthetic", snapshot_date: null,
    });
    expect(r.snapshot_date).toBeNull();
  });
});
