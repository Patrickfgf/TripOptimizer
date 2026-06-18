import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DateFlexControls } from "./DateFlexControls";

describe("DateFlexControls", () => {
  it("emits the chosen start date", () => {
    const onStartDate = vi.fn();
    render(
      <DateFlexControls startDate="2026-07-01" flexDays={3} onStartDate={onStartDate} onFlexDays={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText(/start date/i), { target: { value: "2026-08-15" } });
    expect(onStartDate).toHaveBeenCalledWith("2026-08-15");
  });
  it("shows the current flex value", () => {
    render(
      <DateFlexControls startDate="2026-07-01" flexDays={5} onStartDate={vi.fn()} onFlexDays={vi.fn()} />,
    );
    expect(screen.getByText(/±5/)).toBeInTheDocument();
  });
});
