import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RouteMap } from "./RouteMap";
import { AIRPORTS, RESULT } from "../../test/msw-handlers";

vi.mock("react-simple-maps", () => ({
  ComposableMap: ({ children }: { children: React.ReactNode }) => <svg>{children}</svg>,
  Geographies: ({ children }: { children: (a: { geographies: [] }) => React.ReactNode }) => (
    <g>{children({ geographies: [] })}</g>
  ),
  Geography: () => null,
  Line: (props: Record<string, unknown>) => <line data-testid="leg-line" {...props} />,
  Marker: ({ children }: { children: React.ReactNode }) => <g data-testid="marker">{children}</g>,
}));

describe("RouteMap", () => {
  it("draws a marker per distinct airport and a line per leg", () => {
    render(<RouteMap legs={RESULT.best.legs} airports={AIRPORTS} />);
    expect(screen.getAllByTestId("leg-line")).toHaveLength(RESULT.best.legs.length);
    expect(screen.getAllByTestId("marker")).toHaveLength(4);
  });
});
