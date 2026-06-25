import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Results } from "./Results";
import { AIRPORTS, RESULT } from "../../test/msw-handlers";
import type { TripResult } from "../../lib/schemas";

vi.mock("react-simple-maps", () => ({
  ComposableMap: ({ children }: { children: React.ReactNode }) => <svg>{children}</svg>,
  Geographies: ({ children }: { children: (a: { geographies: [] }) => React.ReactNode }) => (
    <g>{children({ geographies: [] })}</g>
  ),
  Geography: () => null,
  Line: (p: Record<string, unknown>) => <line {...p} />,
  Marker: ({ children }: { children: React.ReactNode }) => <g>{children}</g>,
}));

describe("Results", () => {
  it("renders the best total, timeline and alternatives", () => {
    render(<Results result={RESULT as TripResult} airports={AIRPORTS} />);
    expect(screen.getByText("€214.00")).toBeInTheDocument();
    expect(screen.getByText("LIS → BCN")).toBeInTheDocument();
    expect(screen.getByText(/ROM → BCN/)).toBeInTheDocument();
  });
});
