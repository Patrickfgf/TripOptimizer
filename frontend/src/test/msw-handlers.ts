import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

export const AIRPORTS = [
  { iata: "LIS", name: "Lisbon", city: "Lisbon", country: "PT", lat: 38.77, lon: -9.13 },
  { iata: "BCN", name: "Barcelona", city: "Barcelona", country: "ES", lat: 41.3, lon: 2.08 },
  { iata: "ROM", name: "Rome FCO", city: "Rome", country: "IT", lat: 41.8, lon: 12.25 },
  { iata: "BER", name: "Berlin BER", city: "Berlin", country: "DE", lat: 52.36, lon: 13.5 },
];

export const RESULT = {
  status: "ok",
  best: {
    order: ["BCN", "ROM"],
    start_offset: 0,
    total: 214,
    legs: [
      { origin: "LIS", destination: "BCN", fly_date: "2026-07-01", price: 48, source: "cached" },
      { origin: "BCN", destination: "ROM", fly_date: "2026-07-04", price: 92, source: "cached" },
      { origin: "ROM", destination: "BER", fly_date: "2026-07-06", price: 74, source: "cached" },
    ],
  },
  alternatives: [{ order: ["ROM", "BCN"], start_offset: 0, total: 251, legs: [] }],
  data_source: "cached",
  snapshot_date: "2026-06-15",
};

// Real-or-nothing: no fully-priced route -> honest incomplete result with the gaps.
export const INCOMPLETE = {
  status: "incomplete",
  missing_routes: [
    ["MAD", "DUB"],
    ["FRA", "ATH"],
  ],
  snapshot_date: null,
};

export const handlers = [
  http.get("*/airports", () => HttpResponse.json(AIRPORTS)),
  http.post("*/optimize", () => HttpResponse.json(RESULT)),
  http.get("*/health", () => HttpResponse.json({ status: "ok", airports_loaded: 4, snapshot_date: "2026-06-15" })),
];

export const server = setupServer(...handlers);
