import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ItineraryTimeline } from "./ItineraryTimeline";
import { RESULT } from "../../test/msw-handlers";

describe("ItineraryTimeline", () => {
  it("renders one row per leg with route, fare and source label", () => {
    render(<ItineraryTimeline legs={RESULT.best.legs} />);
    expect(screen.getByText("LIS → BCN")).toBeInTheDocument();
    expect(screen.getByText("€48.00")).toBeInTheDocument();
    expect(screen.getAllByText(/cached/i)).toHaveLength(3);
  });
});
