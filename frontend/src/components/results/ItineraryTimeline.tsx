import type { Leg } from "../../lib/schemas";
import { formatEur } from "../../lib/format";

function SourceChip({ source }: { source: string }) {
  const synthetic = source === "synthetic";
  const cls = synthetic ? "bg-accent-soft text-teal" : "bg-line/60 text-muted";
  return (
    <span
      className={`tabular shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${cls}`}
    >
      {source}
    </span>
  );
}

export function ItineraryTimeline({ legs }: { legs: Leg[] }) {
  return (
    <ol className="overflow-hidden rounded-bento border border-line bg-surface-2 shadow-ticket">
      {legs.map((leg, i) => (
        <li
          key={i}
          className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-dashed border-perf p-4 last:border-b-0"
        >
          <span className="tabular shrink-0 text-xs text-muted">{leg.fly_date}</span>
          <span className="whitespace-nowrap font-semibold sm:min-w-0 sm:flex-1 sm:truncate">
            {leg.origin} &rarr; {leg.destination}
          </span>
          <span className="tabular shrink-0 font-semibold text-ink">{formatEur(leg.price)}</span>
          <SourceChip source={leg.source} />
        </li>
      ))}
    </ol>
  );
}
