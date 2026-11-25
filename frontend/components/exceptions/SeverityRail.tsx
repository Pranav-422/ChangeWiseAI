"use client";
import type { ReactNode } from "react";
import type { ExceptionItem } from "@/lib/api";
import { inr, qty, week, words } from "@/lib/format";
import { Status, cx, toneOf } from "@/components/ui/primitives";

const BAR = { CRITICAL: "bg-critical w-2", HIGH: "bg-high w-1.5", MEDIUM: "bg-pending-mark w-1", LOW: "bg-line-strong w-1" };

/** Exception Severity Rail. The order is Member 1's ranking and is never changed here. */
export function SeverityRail({ items, compact, children }: { items: ExceptionItem[]; compact?: boolean; children?: (item: ExceptionItem) => ReactNode }) {
  return (
    <ol className="divide-y divide-line border-y border-line bg-sheet">
      {items.map((e) => (
        <li key={e.exception_id} className="flex animate-enter">
          <span aria-hidden className={cx("shrink-0", BAR[e.severity_level])} />
          <div className="min-w-0 flex-1 px-4 py-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Status tone={toneOf(e.severity_level)}>{words(e.severity_level)}</Status>
              <span className="font-semibold">{words(e.exception_type)}</span>
              {e.week != null && <span className="mono text-ink-2">{week(e.week)}</span>}
              {e.material_id && <span className="mono text-ink-2">{e.material_id}</span>}
              {!compact && e.status !== "OPEN" && <Status tone={toneOf(e.status)}>{words(e.status)}</Status>}
            </div>
            <p className="mt-1 text-sm text-ink-2">{e.description}</p>
            {!compact && (
              <p className="num mt-1 text-sm text-ink-2">
                {e.quantity != null && <>{qty(e.quantity)} units, </>}
                {e.financial_impact > 0 && <>estimated impact {inr(e.financial_impact)}, </>}
                score {e.severity_score}. Owner: {e.owner_role}. {e.recommended_action}
              </p>
            )}
            {children?.(e)}
          </div>
        </li>
      ))}
    </ol>
  );
}
