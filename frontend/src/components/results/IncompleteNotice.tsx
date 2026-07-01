import { Plane } from "lucide-react";
import type { IncompleteTrip } from "../../lib/schemas";

type Props = { result: IncompleteTrip };

// Honest "real-or-nothing" state: we only show real fares, so when a trip can't be fully
// priced we say so and list the routes with no real fare -- never a fabricated number.
export function IncompleteNotice({ result }: Props) {
  return (
    <section className="animate-ticket-in rounded-bento border border-perf bg-surface-2 p-5 sm:p-6" role="status">
      <h2 className="flex items-center gap-2 text-lg font-extrabold tracking-tight text-ink">
        <Plane className="h-5 w-5 -rotate-45 text-muted" aria-hidden />
        No fully-priced route
      </h2>
      <p className="mt-2 max-w-prose text-sm text-muted">
        We only show real fares, never estimates. We couldn&rsquo;t find a real fare for every
        leg of this trip in your date window, so there&rsquo;s no complete itinerary to price.
        Try nearby dates, fewer cities, or different airports.
      </p>
      {result.missing_routes.length > 0 && (
        <div className="mt-4">
          <span className="text-xs font-semibold uppercase tracking-widest text-muted">
            No real fare found for
          </span>
          <ul className="mt-2 flex flex-wrap gap-2">
            {result.missing_routes.map(([from, to]) => (
              <li
                key={`${from}-${to}`}
                className="tabular rounded-bento-sm border border-line bg-surface px-3 py-1 text-sm font-semibold text-ink"
              >
                {from} &rarr; {to}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
