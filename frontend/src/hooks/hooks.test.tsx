import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithClient } from "../test/render";
import { useAirports } from "./useAirports";

function Probe() {
  const { data, isLoading } = useAirports();
  if (isLoading) return <p>loading</p>;
  return <p>count:{data?.length}</p>;
}

describe("useAirports", () => {
  it("loads airports from the API", async () => {
    renderWithClient(<Probe />);
    expect(await screen.findByText("count:4")).toBeInTheDocument();
  });
});
