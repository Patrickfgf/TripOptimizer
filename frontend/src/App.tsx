import { useEffect, useState } from "react";
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
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-2">
        <span className="font-mono text-sm uppercase tracking-widest text-accent">TripOptimizer</span>
        <h1 className="text-4xl font-bold tracking-tight">Cheapest order for your multi-city trip</h1>
        <p className="text-muted">We reorder your cities and slide the dates to find the lowest total airfare.</p>
      </header>

      <TripForm value={trip} onChange={setTrip} onSubmit={runOptimize} />

      {optimize.isPending && <p className="text-muted">Optimizing&hellip;</p>}
      {optimize.isError && <p className="text-red-700">{(optimize.error as Error).message}</p>}
      {optimize.data && <Results result={optimize.data} airports={airports} />}
    </main>
  );
}
