import Link from "next/link";
import type { ReactNode } from "react";
import type { Run } from "@/lib/api";
import { inr, qty, words } from "@/lib/format";
import { Icon } from "@/components/ui/icons";
import { Status, cx, type Tone } from "@/components/ui/primitives";

export function decisionState(run: Run): { tone: Tone; text: string } {
  if (run.approval) return run.approval.decision === "APPROVED"
    ? { tone: "done", text: `Approved by ${run.approval.user_name}` } : { tone: "critical", text: `Rejected by ${run.approval.user_name}` };
  if (run.stale) return { tone: "pending", text: "Data changed, plan again" };
  if (run.decision === "NO_FEASIBLE_PLAN") return { tone: "critical", text: "No feasible plan" };
  if (run.decision === "INVALID_DATA") return { tone: "critical", text: "Invalid data, not planned" };
  return { tone: "pending", text: "Awaiting planner decision" };
}

/**
 * Optimization Decision Panel. Reads like the objective: shortage first, then E + C. The plan is the engine's rank 1
 * and is shown as proposed, never as approved, until a planner decides.
 */
export function DecisionPanel({ run, action, compact }: { run: Run; action?: ReactNode; compact?: boolean }) {
  const best = run.recommendations[0];
  const state = decisionState(run);
  const broken = run.hard_rules.filter((r) => r.violations > 0).length;
  return (
    <article aria-label="Leading recommendation" className="border border-ink bg-sheet">
      <header className="flex flex-wrap items-center justify-between gap-3 bg-navy-900 px-5 py-3 text-white">
        <p className="flex items-center gap-3">
          <span className="text-sm text-navy-300">{best ? "Engine proposal, rank 1 of " + qty(run.counts.feasible) : "Engine result"}</span>
          {best && <Link href={`/optimization?plan=${best.plan_id}`} className="mono text-navy-100 hover:underline">{best.plan_id}</Link>}
        </p>
        <Status tone={state.tone}>{state.text}</Status>
      </header>
      {best ? (
        <div className={cx("grid", !compact && "lg:grid-cols-[1.15fr_1fr]")}>
          <div className="p-5">
            <p className="display text-[32px]">{best.summary}</p>
            <ol className="mt-5 space-y-0">
              <li className="flex gap-4 border-l-2 border-ink pb-5 pl-4">
                <div className="w-full">
                  <p className="text-sm text-ink-2">First, unmet demand (S)</p>
                  <p className="display text-[36px]">{qty(best.shortage_units)} <span className="text-xl text-ink-2">units</span></p>
                </div>
              </li>
              <li className="flex gap-4 border-l-2 border-line-strong pl-4">
                <div className="w-full">
                  <p className="text-sm text-ink-2">Then, excess plus action cost (E + C)</p>
                  <p className="display text-[36px]">{inr(best.secondary_cost)}</p>
                  <p className="num text-sm text-ink-2">{inr(best.excess_value)} excess inventory and {inr(best.action_cost)} in fees</p>
                </div>
              </li>
            </ol>
          </div>
          <div className={cx("space-y-4 border-line bg-sunken p-5", compact ? "border-t" : "border-t lg:border-t-0 lg:border-l")}>
            {!compact && (
              <div>
                <h3 className="mb-2 text-sm font-semibold">What would be done</h3>
                <ol className="space-y-1.5">
                  {best.summary.split("; ").map((step, i) => (
                    <li key={step} className="flex items-start gap-2"><span className="mono mt-0.5 text-sm text-ink-3">{i + 1}</span>{step}</li>
                  ))}
                  <li className="flex items-start gap-2 text-ink-2"><Icon name="arrow" size={15} className="mt-1" />Rev C takes effect in W{best.effective_week}</li>
                </ol>
              </div>
            )}
            <ul className="space-y-2 text-sm">
              <li className="flex items-start gap-2"><Icon name="check" size={16} className="mt-0.5 text-done" /><span>Breaks none of the {run.hard_rules.length} hard rules. {qty(run.counts.rejected)} other candidates broke {broken} of them.</span></li>
              {best.robustness && (
                <li className="flex items-start gap-2"><Icon name="shield" size={16} className="mt-0.5 text-ink-2" />
                  <span>Covers demand in {best.robustness.display} stress runs.</span></li>
              )}
              {run.escalations.map((e) => (
                <li key={e.code} className="flex items-start gap-2 text-pending"><Icon name="alert" size={16} className="mt-0.5" /><span><strong>{words(e.code)}.</strong> {e.message}</span></li>
              ))}
            </ul>
            {action && <div className="pt-1">{action}</div>}
          </div>
        </div>
      ) : (
        <div className="space-y-3 p-5">
          <p className="display text-2xl">{state.text}</p>
          {run.escalations.map((e) => <p key={e.code} className="text-ink-2">{e.message}</p>)}
          {action}
        </div>
      )}
    </article>
  );
}
