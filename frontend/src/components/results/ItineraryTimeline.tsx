import type { Leg } from "../../lib/schemas";

function SourceChip({ source }: { source: string }) {
  const cls = source === "synthetic" ? "bg-accent-soft text-accent" : "bg-line text-muted";
  return <span className={`tabular rounded-full px-2 py-0.5 text-xs ${cls}`}>{source}</span>;
}

export function ItineraryTimeline({ legs }: { legs: Leg[] }) {
  return (
    <ol className="flex flex-col gap-2">
      {legs.map((leg, i) => (
        <li key={i} className="flex items-center gap-3 rounded-bento border border-line bg-surface-2 p-3">
          <span className="tabular text-sm text-muted">{leg.fly_date}</span>
          <span className="font-medium">
            {leg.origin} &rarr; {leg.destination}
          </span>
          <span className="tabular ml-auto font-semibold">&euro;{leg.price}</span>
          <SourceChip source={leg.source} />
        </li>
      ))}
    </ol>
  );
}
