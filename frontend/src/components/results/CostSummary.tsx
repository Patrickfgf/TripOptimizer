type Props = { total: number; dataSource: "cached" | "synthetic" | "mixed"; snapshotDate: string | null };

export function CostSummary({ total, dataSource, snapshotDate }: Props) {
  return (
    <div className="flex flex-col gap-2 rounded-bento bg-ink p-5 text-surface">
      <span className="text-sm uppercase tracking-wide text-surface/70">Cheapest total</span>
      <span className="tabular text-4xl font-bold text-accent">&euro;{total}</span>
      <p className="text-sm text-surface/80">
        Data: <span className="tabular">{dataSource}</span>
        {snapshotDate ? (
          <>
            {" "}
            &middot; snapshot <span className="tabular">{snapshotDate}</span>
          </>
        ) : null}
      </p>
    </div>
  );
}
