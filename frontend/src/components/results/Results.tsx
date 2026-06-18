import type { Airport, TripResult } from "../../lib/schemas";
import { RouteMap } from "./RouteMap";
import { ItineraryTimeline } from "./ItineraryTimeline";
import { CostSummary } from "./CostSummary";
import { Alternatives } from "./Alternatives";

type Props = { result: TripResult; airports: Airport[] };

export function Results({ result, airports }: Props) {
  return (
    <section className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
      <div className="md:row-span-2">
        <RouteMap legs={result.best.legs} airports={airports} />
      </div>
      <CostSummary total={result.best.total} dataSource={result.data_source} snapshotDate={result.snapshot_date} />
      <div className="flex flex-col gap-4 md:col-span-2">
        <ItineraryTimeline legs={result.best.legs} />
        <Alternatives alternatives={result.alternatives} bestTotal={result.best.total} />
      </div>
    </section>
  );
}
