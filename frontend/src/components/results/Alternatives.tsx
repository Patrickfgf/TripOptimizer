import type { Itinerary } from "../../lib/schemas";
import { formatEur } from "../../lib/format";

type Props = { alternatives: Itinerary[]; bestTotal: number };

export function Alternatives({ alternatives, bestTotal }: Props) {
  if (alternatives.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-muted">Other orderings</h3>
      <ul className="flex flex-col gap-2">
        {alternatives.map((alt, i) => (
          <li
            key={i}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-bento-sm border border-line bg-surface-2 px-4 py-3"
          >
            <span className="min-w-0 flex-1 break-words font-medium">{alt.order.join(" → ")}</span>
            <span className="tabular shrink-0 text-muted">{formatEur(alt.total)}</span>
            <span className="tabular shrink-0 font-semibold text-coral">+{formatEur(alt.total - bestTotal)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
