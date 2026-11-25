"use client";
import Link from "next/link";
import { useWorkspace } from "@/components/layout/Workspace";
import { Empty, LinkButton, Loaded, PageHeading, Section, Status, TableFrame, toneOf } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { dateTime, inr, qty, words } from "@/lib/format";
import { useData } from "@/lib/hooks";

export default function ApprovalsPage() {
  const { can } = useWorkspace();
  const { data, error, mutate } = useData(["approvals"], api.approvals);
  return (
    <>
      <PageHeading title="Approval center" lead="The engine proposes, a planner decides. A decision is final for its run and is recorded here, never sent to an ERP or PLM system." />
      <Loaded data={data} error={error} retry={() => void mutate()}>
        {(list) => (
          <div className="space-y-12">
            <Section title={`Waiting for a decision (${list.pending.length})`}>
              {list.pending.length ? (
                <ul className="space-y-4">{list.pending.map((p) => (
                  <li key={p.run_id} className="grid gap-x-8 gap-y-3 border-l-4 border-pending-mark bg-sheet p-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                    <div>
                      <p className="flex flex-wrap items-center gap-2"><span className="mono font-semibold">{p.change_id}</span>{p.scenario_id !== "base" && <Status tone="pending">{words(p.scenario_id)}</Status>}{p.escalations.map((e) => <Status key={e} tone="pending">{words(e)}</Status>)}</p>
                      <p className="display mt-1 text-2xl">{p.plan_summary}</p>
                      <p className="num text-ink-2">{qty(p.shortage_units)} short, {inr(p.secondary_cost)} E + C, stress runs covered {p.robustness}. Planned {dateTime(p.created_at)}.</p>
                    </div>
                    <LinkButton href={`/approvals/${p.run_id}`} kind="primary" icon="arrow">{can("DECIDE_PLAN") ? "Review and decide" : "Read the case"}</LinkButton>
                  </li>
                ))}</ul>
              ) : <Empty title="Nothing is waiting">Proposals appear here after a planning run.</Empty>}
            </Section>
            <Section title="Decided">
              {list.decided.length ? (
                <TableFrame label="Decisions">
                  <thead><tr><th>Decision</th><th>Change</th><th>Plan</th><th>Comment</th><th>Decided by</th><th>When</th><th>Closed</th></tr></thead>
                  <tbody>{list.decided.map((a) => (
                    <tr key={a.approval_id}><td><Link href={`/approvals/${a.run_id}`}><Status tone={toneOf(a.decision)}>{words(a.decision)}</Status></Link></td><td className="mono">{a.change_id}{a.scenario_id !== "base" && <span className="block text-[13px] text-pending">{words(a.scenario_id)}</span>}</td><td>{a.plan_summary ?? "None"}{a.modified && <span className="block text-[13px] text-ink-3">Modified by the planner</span>}</td><td className="max-w-72">{a.comment || "–"}</td><td>{a.user_name}<span className="block text-[13px] text-ink-3">{a.role}</span></td><td>{dateTime(a.created_at)}</td><td>{dateTime(a.closed_at)}</td></tr>
                  ))}</tbody>
                </TableFrame>
              ) : <p className="text-ink-2">No decision has been made yet.</p>}
            </Section>
          </div>
        )}
      </Loaded>
    </>
  );
}
