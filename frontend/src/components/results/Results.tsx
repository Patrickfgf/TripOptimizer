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
    <section className="flex flex-col gap-4">
      <CostSummary total={result.best.total} dataSource={result.data_source} snapshotDate={result.snapshot_date} />
      <div className="grid gap-4 md:grid-cols-[1.1fr_1fr]">
        <Suspense
          fallback={<div className="aspect-[4/3] rounded-bento border border-line bg-surface-2" aria-busy="true" />}
        >
          <RouteMap legs={result.best.legs} airports={airports} />
        </Suspense>
        <ItineraryTimeline legs={result.best.legs} />
      </div>
      <Alternatives alternatives={result.alternatives} bestTotal={result.best.total} />
    </section>
  );
}
