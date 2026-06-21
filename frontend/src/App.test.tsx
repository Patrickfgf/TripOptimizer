import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithClient } from "./test/render";
import App from "./App";

vi.mock("react-simple-maps", () => ({
  ComposableMap: ({ children }: { children: React.ReactNode }) => <svg>{children}</svg>,
  Geographies: ({ children }: { children: (a: { geographies: [] }) => React.ReactNode }) => (
    <g>{children({ geographies: [] })}</g>
  ),
  Geography: () => null,
  Line: (p: Record<string, unknown>) => <line {...p} />,
  Marker: ({ children }: { children: React.ReactNode }) => <g>{children}</g>,
}));

beforeEach(() => {
  window.history.replaceState({}, "", "/");
});

describe("App", () => {
  it("optimizes after the user fills the form and shows the result", async () => {
    renderWithClient(<App />);
    await userEvent.click(await screen.findByRole("combobox", { name: /^origin$/i }));
    await userEvent.click(await screen.findByText(/Lisbon/i));
    await userEvent.click(screen.getByRole("combobox", { name: /^return$/i }));
    await userEvent.click(await screen.findByText(/Berlin/i));
    await userEvent.click(screen.getByRole("combobox", { name: /add a city/i }));
    await userEvent.click(await screen.findByText(/Barcelona/i));
    fireEvent.change(screen.getByLabelText(/start date/i), { target: { value: "2026-07-01" } });
    await userEvent.click(screen.getByRole("button", { name: /optimize route/i }));
    expect(await screen.findByText("€214")).toBeInTheDocument();
  });
});
