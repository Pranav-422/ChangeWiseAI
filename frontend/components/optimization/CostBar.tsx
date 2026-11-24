import { inr } from "@/lib/format";

/** Excess value and action cost of several options on one scale. */
export function CostBars({ rows }: { rows: { name: string; detail?: string; excess: number; action: number; total: number; emphasis?: boolean }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.total));
  return (
    <div>
      <div className="mb-2 flex gap-4 text-[13px] text-ink-2">
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-3 bg-navy-700" />Excess inventory value (E)</span>
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-3 bg-tech" />Action cost (C)</span>
      </div>
      <ul className="space-y-3">
        {rows.map((r) => (
          <li key={r.name}>
            <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3">
              <span className={r.emphasis ? "font-semibold" : ""}>{r.name}{r.detail && <span className="ml-2 text-sm font-normal text-ink-2">{r.detail}</span>}</span>
              <span className="num font-semibold">{inr(r.total)}</span>
            </div>
            <div className="flex h-4 gap-0.5 bg-neutral-soft" role="img" aria-label={`${r.name}: excess ${inr(r.excess)}, action cost ${inr(r.action)}`}>
              {r.excess > 0 && <div title={`Excess ${inr(r.excess)}`} className="bg-navy-700 transition-[width] duration-300" style={{ width: `${(r.excess / max) * 100}%` }} />}
              {r.action > 0 && <div title={`Action cost ${inr(r.action)}`} className="rounded-r-soft bg-tech transition-[width] duration-300" style={{ width: `${(r.action / max) * 100}%` }} />}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
