import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { getAirports, optimize } from "./api";
import { INCOMPLETE, server } from "../test/msw-handlers";

const REQ = {
  origin_airport: "LIS",
  return_airport: "BER",
  cities: ["BCN", "ROM"],
  days_per_city: { BCN: 3, ROM: 2 },
  start_date: "2026-07-01",
  flex_days: 3,
};

describe("api client", () => {
  it("getAirports returns parsed airports", async () => {
    const airports = await getAirports();
    expect(airports).toHaveLength(4);
    expect(airports[0].iata).toBe("LIS");
  });

  it("optimize returns a parsed ok result", async () => {
    const res = await optimize(REQ);
    expect(res.status).toBe("ok");
    if (res.status === "ok") {
      expect(res.best.total).toBe(214);
      expect(res.data_source).toBe("cached");
    }
  });

  it("optimize parses an honest incomplete result", async () => {
    server.use(http.post("*/optimize", () => HttpResponse.json(INCOMPLETE)));
    const res = await optimize(REQ);
    expect(res.status).toBe("incomplete");
    if (res.status === "incomplete") {
      expect(res.missing_routes).toHaveLength(2);
    }
  });
});
