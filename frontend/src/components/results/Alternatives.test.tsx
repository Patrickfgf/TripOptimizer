import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Alternatives } from "./Alternatives";
import type { Itinerary } from "../../lib/schemas";

const ALTS: Itinerary[] = [
  { order: ["ROM", "BCN"], start_offset: 0, total: 251, legs: [] },
  { order: ["BCN", "ROM"], start_offset: 1, total: 268, legs: [] },
];

describe("Alternatives", () => {
  it("lists alternatives with the delta vs the best total", () => {
    render(<Alternatives alternatives={ALTS} bestTotal={214} />);
    expect(screen.getByText(/ROM → BCN/)).toBeInTheDocument();
    expect(screen.getByText("+€37.00")).toBeInTheDocument();
    expect(screen.getByText("+€54.00")).toBeInTheDocument();
  });
  it("renders nothing when there are no alternatives", () => {
    const { container } = render(<Alternatives alternatives={[]} bestTotal={214} />);
    expect(container).toBeEmptyDOMElement();
  });
});
