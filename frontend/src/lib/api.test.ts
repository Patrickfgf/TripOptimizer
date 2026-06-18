import { describe, it, expect } from "vitest";
import { getAirports, optimize } from "./api";

describe("api client", () => {
  it("getAirports returns parsed airports", async () => {
    const airports = await getAirports();
    expect(airports).toHaveLength(4);
    expect(airports[0].iata).toBe("LIS");
  });
  it("optimize returns a parsed TripResult", async () => {
    const res = await optimize({
      origin_airport: "LIS",
      return_airport: "BER",
      cities: ["BCN", "ROM"],
      days_per_city: { BCN: 3, ROM: 2 },
      start_date: "2026-07-01",
      flex_days: 3,
    });
    expect(res.best.total).toBe(214);
    expect(res.data_source).toBe("mixed");
  });
});
