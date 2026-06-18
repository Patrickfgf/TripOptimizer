import { z } from "zod";
import { AirportSchema, TripResultSchema, type Airport, type TripRequest, type TripResult } from "./schemas";

// Empty base URL -> relative paths hit the Vite dev proxy (/api). Set VITE_API_BASE_URL in prod.
export function apiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  return base ? base.replace(/\/$/, "") : "/api";
}

async function getJson<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${apiBaseUrl()}${path}`, init);
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* non-JSON body */
    }
    throw new Error(detail);
  }
  return schema.parse(await resp.json());
}

export function getAirports(): Promise<Airport[]> {
  return getJson("/airports", z.array(AirportSchema));
}

export function getHealth() {
  return getJson(
    "/health",
    z.object({ status: z.string(), airports_loaded: z.number(), snapshot_date: z.string().nullable() }),
  );
}

export function optimize(req: TripRequest): Promise<TripResult> {
  return getJson("/optimize?engine=bruteforce", TripResultSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}
