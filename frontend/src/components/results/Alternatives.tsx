import type { Itinerary } from "../../lib/schemas";

type Props = { alternatives: Itinerary[]; bestTotal: number };

export function Alternatives({ alternatives, bestTotal }: Props) {
  if (alternatives.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm uppercase tracking-wide text-muted">Other orderings</h3>
      {alternatives.map((alt, i) => (
        <div key={i} className="flex items-center gap-3 rounded-bento border border-line bg-surface-2 p-3">
          <span className="font-medium">{alt.order.join(" → ")}</span>
          <span className="tabular ml-auto text-muted">&euro;{alt.total}</span>
          <span className="tabular text-accent">+&euro;{alt.total - bestTotal}</span>
        </div>
      ))}
    </div>
  );
}
