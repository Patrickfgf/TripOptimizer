import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { IncompleteNotice } from "./IncompleteNotice";

describe("IncompleteNotice", () => {
  it("shows the honest heading and lists the missing routes (no price)", () => {
    render(
      <IncompleteNotice
        result={{
          status: "incomplete",
          missing_routes: [
            ["MAD", "DUB"],
            ["FRA", "ATH"],
          ],
          snapshot_date: null,
        }}
      />,
    );
    expect(screen.getByText(/no fully-priced route/i)).toBeInTheDocument();
    expect(screen.getByText(/MAD\s*→\s*DUB/)).toBeInTheDocument();
    expect(screen.getByText(/FRA\s*→\s*ATH/)).toBeInTheDocument();
  });
});
