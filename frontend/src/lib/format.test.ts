import { describe, it, expect } from "vitest";
import { formatEur } from "./format";

describe("formatEur", () => {
  it("formats with the euro symbol and exactly two decimals", () => {
    expect(formatEur(214)).toBe("€214.00");
    expect(formatEur(48)).toBe("€48.00");
  });

  it("caps long floating-point tails at two decimals", () => {
    expect(formatEur(50.98984978742)).toBe("€50.99");
  });

  it("tames float subtraction (the alternatives delta)", () => {
    expect(formatEur(251 - 214)).toBe("€37.00");
  });

  it("adds a thousands separator for larger totals", () => {
    expect(formatEur(1234.5)).toBe("€1,234.50");
  });

  it("formats zero", () => {
    expect(formatEur(0)).toBe("€0.00");
  });
});
