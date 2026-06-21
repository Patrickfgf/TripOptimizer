import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CityList } from "./CityList";

const CITIES = [
  { iata: "BCN", days: 3 },
  { iata: "ROM", days: 2 },
];

describe("CityList", () => {
  it("renders each city with its days", () => {
    render(<CityList cities={CITIES} onChange={vi.fn()} />);
    expect(screen.getByText("BCN")).toBeInTheDocument();
    expect(screen.getByLabelText("days for BCN")).toHaveValue(3);
  });
  it("removes a city", async () => {
    const onChange = vi.fn();
    render(<CityList cities={CITIES} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "remove ROM" }));
    expect(onChange).toHaveBeenCalledWith([{ iata: "BCN", days: 3 }]);
  });
  it("changes days for a city", () => {
    // CityList is controlled; a single change event is the correct unit-level assertion.
    const onChange = vi.fn();
    render(<CityList cities={CITIES} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("days for BCN"), { target: { value: "5" } });
    expect(onChange).toHaveBeenCalledWith([
      { iata: "BCN", days: 5 },
      { iata: "ROM", days: 2 },
    ]);
  });
});
