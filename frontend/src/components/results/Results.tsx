import { lazy, Suspense } from "react";
import type { Airport, TripResult } from "../../lib/schemas";
import { ItineraryTimeline } from "./ItineraryTimeline";
import { CostSummary } from "./CostSummary";
import { Alternatives } from "./Alternatives";

// The route map pulls in react-simple-maps + the world-atlas TopoJSON — a heavy
// chunk. Lazy-load it so it never blocks the initial bundle / first paint.
const RouteMap = lazy(() => import("./RouteMap").then((m) => ({ default: m.RouteMap })));

type Props = { result: TripResult; airports: Airport[] };

export function Results({ result, airports }: Props) {
  return (
    <section className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
      <div className="md:row-span-2">
        <Suspense
          fallback={<div className="aspect-square rounded-bento border border-line bg-surface-2" aria-busy="true" />}
        >
          <RouteMap legs={result.best.legs} airports={airports} />
        </Suspense>
      </div>
      <CostSummary total={result.best.total} dataSource={result.data_source} snapshotDate={result.snapshot_date} />
      <div className="flex flex-col gap-4 md:col-span-2">
        <ItineraryTimeline legs={result.best.legs} />
        <Alternatives alternatives={result.alternatives} bestTotal={result.best.total} />
      </div>
    </section>
  );
}
