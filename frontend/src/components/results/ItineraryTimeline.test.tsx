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

  it("links each leg to a one-way Aviasales search opening in a new tab", () => {
    render(<ItineraryTimeline legs={RESULT.best.legs} />);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(3);
    // LIS -> BCN on 2026-07-01 => ORIGIN + DD + MM + DEST + pax
    expect(links[0]).toHaveAttribute("href", "https://www.aviasales.com/search/LIS0107BCN1");
    expect(links[2]).toHaveAttribute("href", "https://www.aviasales.com/search/ROM0607BER1");
    expect(links[0]).toHaveAttribute("target", "_blank");
    expect(links[0]).toHaveAttribute("rel", "noopener noreferrer");
    // New-tab behavior must be announced to assistive tech (the icon is aria-hidden).
    expect(links[0]).toHaveAccessibleName(/opens in new tab/i);
  });
});
