import { ExternalLink } from "lucide-react";
import type { Leg } from "../../lib/schemas";
import { formatEur } from "../../lib/format";
import { aviasalesSearchUrl } from "../../lib/bookingLink";

function SourceChip({ source }: { source: string }) {
  return (
    <span
      className="tabular shrink-0 rounded-full bg-line/60 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted"
    >
      {source}
    </span>
  );
}

function SearchLink({ leg }: { leg: Leg }) {
  return (
    <a
      href={aviasalesSearchUrl(leg.origin, leg.destination, leg.fly_date)}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Search ${leg.origin} to ${leg.destination} flights on ${leg.fly_date} (opens in new tab)`}
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-teal/40 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-teal transition-colors hover:bg-teal hover:text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/50"
    >
      Search
      <ExternalLink className="h-3 w-3" aria-hidden />
    </a>
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
          <SearchLink leg={leg} />
        </li>
      ))}
    </ol>
  );
}
