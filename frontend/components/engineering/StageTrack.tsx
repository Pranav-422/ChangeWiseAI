import { Icon } from "@/components/ui/icons";
import { cx } from "@/components/ui/primitives";

export const STAGES = ["ECN received", "Validated", "Plan approved", "Actions done", "Closed"];

/** Lifecycle of the change. `done` is the number of finished stages, as the backend reports it. */
export function StageTrack({ done }: { done: number }) {
  return (
    <ol aria-label={`${done} of ${STAGES.length} stages finished`} className="flex min-w-0 flex-wrap gap-y-2">
      {STAGES.map((stage, i) => {
        const state = i < done ? "done" : i === done ? "next" : "later";
        return (
          <li key={stage} aria-current={state === "next" ? "step" : undefined} className="flex items-center gap-2 pr-3 text-sm">
            <span className={cx("flex size-5 items-center justify-center rounded-full border text-[11px]",
              state === "done" ? "border-done bg-done text-white" : state === "next" ? "border-tech text-tech" : "border-line-strong text-ink-3")}>
              {state === "done" ? <Icon name="check" size={12} strokeWidth={2.6} /> : <span className="mono">{i + 1}</span>}
            </span>
            <span className={cx(state === "next" ? "font-semibold" : state === "later" && "text-ink-3")}>{stage}</span>
            {i < STAGES.length - 1 && <span aria-hidden className={cx("h-px w-5", i < done ? "bg-done" : "bg-line-strong")} />}
          </li>
        );
      })}
    </ol>
  );
}
