import { describe, it, expect } from "vitest";
import { aviasalesSearchUrl } from "./bookingLink";

describe("aviasalesSearchUrl", () => {
  it("builds a one-way search URL in ORIGIN+DD+MM+DEST+passengers order", () => {
    expect(aviasalesSearchUrl("LON", "LIS", "2026-08-12")).toBe(
      "https://www.aviasales.com/search/LON1208LIS1",
    );
  });

  it("puts the day before the month (Aviasales is DDMM, not MMDD)", () => {
    // 2026-01-05 -> day 05, month 01 -> "0501", NOT "0105"
    expect(aviasalesSearchUrl("LIS", "BCN", "2026-01-05")).toBe(
      "https://www.aviasales.com/search/LIS0501BCN1",
    );
  });

  it("uppercases IATA codes so casing from the API can't break the link", () => {
    expect(aviasalesSearchUrl("cdg", "fco", "2026-12-09")).toBe(
      "https://www.aviasales.com/search/CDG0912FCO1",
    );
  });
});
