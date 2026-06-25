import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CostSummary } from "./CostSummary";

describe("CostSummary", () => {
  it("shows total, data source and snapshot date", () => {
    render(<CostSummary total={214} dataSource="mixed" snapshotDate="2026-06-15" />);
    expect(screen.getByText("€214.00")).toBeInTheDocument();
    expect(screen.getByText(/mixed/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-06-15/)).toBeInTheDocument();
  });
  it("handles a null snapshot date", () => {
    render(<CostSummary total={0} dataSource="synthetic" snapshotDate={null} />);
    expect(screen.getByText(/synthetic/i)).toBeInTheDocument();
  });
});
