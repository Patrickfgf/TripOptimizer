import { useEffect, useState } from "react";
import { Plane } from "lucide-react";
import { TripForm } from "./components/trip-form/TripForm";
import { Results } from "./components/results/Results";
import { useAirports } from "./hooks/useAirports";
import { useOptimize } from "./hooks/useOptimize";
import { decodeTrip, encodeTrip, toApiRequest, type TripInput } from "./lib/urlState";

const EMPTY: TripInput = {
  origin_airport: "",
  return_airport: "",
  cities: [],
  start_date: "",
  flex_days: 3,
};

export default function App() {
  const { data: airports = [] } = useAirports();
  const optimize = useOptimize();
  const [trip, setTrip] = useState<TripInput>(() => decodeTrip(window.location.search) ?? EMPTY);

  const runOptimize = (t: TripInput) => {
    window.history.replaceState({}, "", encodeTrip(t));
    optimize.mutate(toApiRequest(t));
  };

  // Auto-run once if the URL carried a complete trip.
  useEffect(() => {
    if (decodeTrip(window.location.search)) runOptimize(trip);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12">
      <header className="flex flex-col gap-3">
        <span className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-[0.25em] text-teal">
          <Plane className="h-4 w-4 -rotate-45" aria-hidden /> TripOptimizer
        </span>
        <h1 className="max-w-2xl text-3xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl">
          The cheapest <span className="text-teal">order</span> for your multi-city trip
        </h1>
        <p className="max-w-xl text-muted">
          We reorder your cities and slide the dates to find the lowest total airfare.
        </p>
      </header>

      <TripForm value={trip} onChange={setTrip} onSubmit={runOptimize} />

      {optimize.isPending && <p className="tabular animate-pulse text-sm text-muted">Optimizing&hellip;</p>}
      {optimize.isError && (
        <p className="rounded-bento-sm border border-coral/40 bg-coral/10 px-4 py-3 text-sm font-medium text-coral">
          {(optimize.error as Error).message}
        </p>
      )}
      {optimize.data && <Results result={optimize.data} airports={airports} />}
    </main>
  );
}
