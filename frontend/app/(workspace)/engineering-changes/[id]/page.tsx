"use client";
import Link from "next/link";
import { use, useEffect } from "react";
import { RevisionRibbon } from "@/components/engineering/RevisionRibbon";
import { StageTrack } from "@/components/engineering/StageTrack";
import { useWorkspace } from "@/components/layout/Workspace";
import { decisionState } from "@/components/optimization/DecisionPanel";
import { Alert, Empty, Facts, LinkButton, Loaded, PageHeading, Section, Status, TableFrame, toneOf } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { dateTime, inr, qty, week, words } from "@/lib/format";
import { useData } from "@/lib/hooks";

export default function ChangeWorkspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { change, changes, scenario, select, can } = useWorkspace();
  const known = changes.some((c) => c.change_id === id);
  useEffect(() => { if (known && change.change_id !== id) select(id, "base"); }, [known, id, change.change_id, select]);
  const { data, error, mutate } = useData(known ? ["overview", id, scenario] : null, () => api.overview(id, scenario));
  if (!known) return <Empty title={`${id} is not in the planning records`} action={<LinkButton href="/engineering-changes">All changes</LinkButton>} />;
  return (
    <Loaded data={data} error={error} retry={() => void mutate()}>
      {(o) => {
        const c = o.change, state = o.run && decisionState(o.run);
        return (
          <>
            <PageHeading title={`${c.change_id}: ${c.reason ?? c.part_number}`}
              lead={<>Replaces <span className="mono">{c.part_number}</span> {c.old_revision} with <span className="mono">{c.new_material_id}</span> {c.new_revision}.</>}
              action={<>{can("VIEW_DOCUMENTS") && o.latest_review && <LinkButton href={`/ecn/${o.latest_review.review_id}`}>Document review</LinkButton>}{o.run && <LinkButton href="/optimization" kind="primary">Planning result</LinkButton>}</>} />
            <div className="space-y-12">
              <div className="grid gap-12 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
                <Section title="Transition">
                  <RevisionRibbon from={c.old_revision} to={c.new_revision} effectiveWeek={c.effective_week} useUpEnd={c.use_up_end_week} horizon={o.inventory.horizon_weeks} interchangeable={c.interchangeability} />
                  <div className="mt-6"><StageTrack done={o.stage} /></div>
                </Section>
                <Section title="Record">
                  <Facts items={[["Effective week", <span key="e" className="mono">{week(c.effective_week)}</span>], ["Use-up end week", <span key="u" className="mono">{week(c.use_up_end_week)}</span>],
                    ["Interchangeable", c.interchangeability ? "Yes" : "No"], ["Approval", <Status key="a" tone={toneOf(c.approval_status)}>{c.approval_status}</Status>],
                    ["Approver", c.approver ?? "Not recorded"], ["Approval week", <span key="w" className="mono">{week(c.approval_week)}</span>]]} />
                </Section>
              </div>
              <Section title="Record check" note="Member 1's validation of the planning records for this change.">
                {o.validation.issues.length === 0 ? <Alert kind="done">Nothing to correct.</Alert> : (
                  <div className="space-y-2">{o.validation.issues.map((i) => (
                    <Alert key={i.code + i.record} kind={i.status === "NEEDS_REVIEW" ? "warning" : "critical"} title={`${words(i.code)}, ${i.record}`}>{i.description} {i.resolution}</Alert>
                  ))}</div>
                )}
              </Section>
              <Section title="Stock and orders of the two materials">
                <div className="grid gap-8 lg:grid-cols-2">
                  <TableFrame label="Stock">
                    <thead><tr><th>Material</th><th>On hand</th><th>Reserved</th><th>Safety stock</th><th>Unit cost</th></tr></thead>
                    <tbody>{o.inventory.materials.map((m) => {
                      const s = o.inventory.stock.find((x) => x.material_id === m.material_id);
                      return <tr key={m.material_id} className="num"><td><span className="mono">{m.material_id}</span> {m.revision}</td><td>{qty(s?.on_hand)}</td><td>{qty(s?.reserved)}</td><td>{qty(s?.safety_stock)}</td><td>{inr(m.unit_cost)}</td></tr>;
                    })}</tbody>
                  </TableFrame>
                  <TableFrame label="Purchase orders">
                    <thead><tr><th>Order</th><th>Material</th><th>Supplier</th><th>Quantity</th><th>Arrives</th></tr></thead>
                    <tbody>{o.inventory.purchase_orders.map((p) => (
                      <tr key={p.po_id} className="num"><td className="mono">{p.po_id}</td><td className="mono">{p.material_id}</td><td>{p.supplier_id} <Status tone={p.supplier_status === "Approved" ? "done" : "critical"}>{p.supplier_status}</Status></td><td>{qty(p.quantity)}</td><td className="mono">{week(p.arrival_week)}</td></tr>
                    ))}</tbody>
                  </TableFrame>
                </div>
              </Section>
              <Section title="Planning and decision">
                {o.run && state ? (
                  <Facts columns={3} items={[["Run", <Link key="r" href="/optimization" className="mono text-tech hover:underline">{o.run.run_id}</Link>], ["Planned", `${dateTime(o.run.created_at)} by ${o.run.created_by}`],
                    ["State", <Status key="s" tone={state.tone}>{state.text}</Status>], ["Leading plan", o.run.recommendations[0]?.summary ?? "None"],
                    ["Unmet demand", qty(o.run.recommendations[0]?.shortage_units)], ["Excess plus action cost", inr(o.run.recommendations[0]?.secondary_cost)]]} />
                ) : <Empty title="Not planned yet">Confirm the ECN, then run the optimization.</Empty>}
              </Section>
            </div>
          </>
        );
      }}
    </Loaded>
  );
}
