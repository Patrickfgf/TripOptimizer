import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AirportCombobox } from "./AirportCombobox";
import { AIRPORTS } from "../../test/msw-handlers";

describe("AirportCombobox", () => {
  it("selects an airport and calls onChange with its IATA", async () => {
    const onChange = vi.fn();
    render(<AirportCombobox airports={AIRPORTS} value={null} onChange={onChange} label="Origin" />);
    await userEvent.click(screen.getByRole("combobox", { name: /origin/i }));
    await userEvent.click(await screen.findByText(/Barcelona/i));
    expect(onChange).toHaveBeenCalledWith("BCN");
  });
});
