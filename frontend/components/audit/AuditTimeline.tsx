"use client";
import type { AuditEvent } from "@/lib/api";
import { day, words } from "@/lib/format";
import { cx } from "@/components/ui/primitives";

const DOT: Record<string, string> = {
  PLAN_APPROVED: "bg-done border-done", CHANGE_CLOSED: "bg-done border-done", ECN_CONFIRMED: "bg-done border-done",
  PLAN_REJECTED: "bg-critical border-critical", EXTRACTION_FAILED: "bg-critical border-critical",
  PLAN_GENERATED: "bg-tech border-tech", RUN_REPLAYED: "bg-tech border-tech", SIMULATION_RUN: "bg-tech border-tech",
};

function note(e: AuditEvent): string {
  const p = e.payload as Record<string, unknown>;
  const pick = (...keys: string[]) => keys.map((k) => p[k]).find((v) => typeof v === "string" && v) as string | undefined;
  switch (e.event_type) {
    case "ACTION_STATUS": case "EXCEPTION_STATUS": return `${words(String(p.from))} to ${words(String(p.to)).toLowerCase()}`;
    case "PLAN_GENERATED": return `${words(String(p.decision))}${p.recommended_plan_id ? `, ${p.recommended_plan_id}` : ""}`;
    case "RUN_REPLAYED": return p.matches ? "Result reproduced exactly" : "Result differs";
    case "ECN_EDITED": return `Changed ${Object.keys((p.changes as object) ?? {}).map((k) => words(k).toLowerCase()).join(", ")}`;
    case "PLAN_MODIFIED": return `${p.plan_id}, ${words(String(p.feasibility)).toLowerCase()}`;
    default: return pick("comment", "summary", "filename", "question", "reason", "validation", "status", "label") ?? "";
  }
}

/** Decision Audit Timeline, newest first, grouped by day. */
export function AuditTimeline({ events, onSelect, compact }: { events: AuditEvent[]; onSelect?: (e: AuditEvent) => void; compact?: boolean }) {
  return (
    <ol className="relative ml-1.5 border-l border-line-strong">
      {events.map((e, i) => {
        const date = day(e.created_at), heading = !events[i - 1] || date !== day(events[i - 1]!.created_at);
        const body = (
          <>
            <span className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-semibold">{words(e.event_type)}</span>
              <span className="mono text-[13px] text-ink-3">{e.entity_id}</span>
            </span>
            {note(e) && <span className="block truncate text-sm text-ink-2">{note(e)}</span>}
            <span className="block text-[13px] text-ink-3">
              <time dateTime={e.created_at}>{new Date(e.created_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</time>, {e.user_name} ({e.role})
            </span>
          </>
        );
        return (
          <li key={e.seq} className={cx("relative pl-5", compact ? "pb-3" : "pb-4")}>
            {heading && !compact && <p className="tag mb-2 pt-1">{date}</p>}
            <span aria-hidden className={cx("absolute -left-[5.5px] mt-1.5 size-2.5 rounded-full border-2", DOT[e.event_type] ?? "border-ink-3 bg-sheet")} />
            {onSelect ? <button type="button" onClick={() => onSelect(e)} className="block w-full min-w-0 text-left hover:bg-sunken">{body}</button> : <div className="min-w-0">{body}</div>}
          </li>
        );
      })}
    </ol>
  );
}
