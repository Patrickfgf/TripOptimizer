import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithClient } from "../../test/render";
import { TripForm } from "./TripForm";
import type { TripInput } from "../../lib/urlState";

const TRIP: TripInput = {
  origin_airport: "LIS",
  return_airport: "BER",
  cities: [{ iata: "BCN", days: 3 }],
  start_date: "2026-07-01",
  flex_days: 3,
};

describe("TripForm", () => {
  it("submits a valid trip", async () => {
    const onSubmit = vi.fn();
    renderWithClient(<TripForm value={TRIP} onChange={vi.fn()} onSubmit={onSubmit} />);
    await userEvent.click(await screen.findByRole("button", { name: /optimize route/i }));
    expect(onSubmit).toHaveBeenCalledWith(TRIP);
  });

  it("disables submit when there are no cities", async () => {
    renderWithClient(<TripForm value={{ ...TRIP, cities: [] }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(await screen.findByRole("button", { name: /optimize route/i })).toBeDisabled();
  });
});
