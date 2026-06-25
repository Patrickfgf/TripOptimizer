import { Plane } from "lucide-react";
import { formatEur } from "../../lib/format";

type Props = { total: number; dataSource: "cached" | "synthetic" | "mixed"; snapshotDate: string | null };

export function CostSummary({ total, dataSource, snapshotDate }: Props) {
  return (
    <div className="animate-ticket-in relative overflow-hidden rounded-bento bg-surface-2 shadow-ticket">
      <div className="flex items-center justify-between bg-navy px-5 py-3 text-surface">
        <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em]">
          <Plane className="h-4 w-4 -rotate-45" aria-hidden /> Boarding pass
        </span>
        <span className="tabular text-[11px] uppercase tracking-widest text-surface/70">Cheapest route</span>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-stretch">
        <div className="flex flex-1 flex-col gap-1 p-5">
          <span className="text-xs font-semibold uppercase tracking-widest text-muted">Cheapest total</span>
          <span className="tabular text-4xl font-extrabold leading-none text-ink sm:text-5xl">{formatEur(total)}</span>
          <p className="mt-2 text-sm text-muted">
            Fares: <span className="tabular font-semibold text-teal">{dataSource}</span>
            {snapshotDate ? (
              <>
                {" · snapshot "}
                <span className="tabular">{snapshotDate}</span>
              </>
            ) : null}
          </p>
        </div>

        {/* tear line: horizontal on mobile, vertical + punched notches on desktop */}
        <div className="mx-5 border-t-2 border-dashed border-perf sm:hidden" aria-hidden />
        <div className="relative hidden w-0 sm:block" aria-hidden>
          <div className="absolute inset-y-4 left-0 border-l-2 border-dashed border-perf" />
          <span className="absolute -top-2 left-0 h-4 w-4 -translate-x-1/2 rounded-full bg-surface" />
          <span className="absolute -bottom-2 left-0 h-4 w-4 -translate-x-1/2 rounded-full bg-surface" />
        </div>

        <div className="flex items-center justify-center gap-3 p-5 sm:w-40 sm:flex-col">
          <div className="w-full text-navy">
            <div className="barcode h-12 w-full sm:h-16" aria-hidden />
          </div>
          <span className="shrink-0 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted">
            EUR · economy
          </span>
        </div>
      </div>
    </div>
  );
}
