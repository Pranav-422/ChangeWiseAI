"use client";
import { useState } from "react";
import { BalanceBar } from "@/components/inventory/BalanceBar";
import { DemandCoverage, StockBalance } from "@/components/inventory/charts";
import { MaterialFlow } from "@/components/inventory/MaterialFlow";
import { useWorkspace } from "@/components/layout/Workspace";
import { Tabs } from "@/components/ui/overlay";
import { Alert, Button, Empty, ErrorNote, Loaded, Metric, PageHeading, Section, Status, TableFrame, cx } from "@/components/ui/primitives";
import { api, type Overview, type Week } from "@/lib/api";
import { dateTime, inr, qty, units, week, weekRange, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

export default function InventoryPage() {
  const { change, scenario } = useWorkspace();
  const { data, error, mutate } = useData(["overview", change.change_id, scenario], () => api.overview(change.change_id, scenario));
  return <Loaded data={data} error={error} retry={() => void mutate()}>{(o) => <Monitor key={o.inventory.simulation_id} o={o} />}</Loaded>;
}

function Monitor({ o }: { o: Overview }) {
  const { can, change: selected, scenario } = useWorkspace();
  const { run, pending, error } = useAction();
  const { inventory: inv, change } = o;
  const [view, setView] = useState("base");
  const plans = o.run && !o.run.stale ? o.run.recommendations : [];
  const plan = plans.find((p) => p.plan_id === view);
  const weeks = plan?.weekly ?? inv.weeks;
  const shortage = plan ? plan.shortage_units : inv.total_shortage_units;
  const excess = plan ? plan.excess_value : inv.excess_value;
  const short = weeks.filter((w) => w.shortage > 0);
  const last = weeks.at(-1);
  return (
    <>
      <PageHeading title="Inventory monitor"
        lead={weeks.length ? short.length ? `${units(shortage)} of demand are unmet in ${weekRange(short.map((w) => w.week))}.` : "Every week's demand is met. Watch what is left when the old revision ends." : "The records are too incomplete to simulate."}
        action={can("RUN_SIMULATION") && <Button icon="replay" busy={pending === "simulate"} onClick={() => run("simulate", () => api.simulate(selected.change_id, scenario))}>Run and store simulation</Button>} />
      {error && <div className="mb-6"><ErrorNote error={error} /></div>}
      {!weeks.length ? (
        <div className="space-y-2">{inv.issues.map((i) => <Alert key={i.code + i.record} kind="critical" title={words(i.code)}>{i.description} {i.resolution}</Alert>)}{!inv.issues.length && <Empty title="No simulation" />}</div>
      ) : (
        <div className="space-y-12">
          <Section title="Transition by week" note={`Simulation ${inv.simulation_id}, engine ${inv.engine_version}, ${inv.stored_at ? `stored ${dateTime(inv.stored_at)}` : "calculated now, not stored"}`}
            action={plans.length > 0 && (
              <div role="group" aria-label="Show" className="flex flex-wrap gap-1">
                {[{ id: "base", title: "No action" }, ...plans.map((p) => ({ id: p.plan_id, title: `Plan ${p.rank}` }))].map((t) => (
                  <button key={t.id} type="button" aria-pressed={view === t.id} onClick={() => setView(t.id)}
                    className={cx("min-h-9 border px-3 text-sm font-semibold", view === t.id ? "border-ink bg-navy-900 text-white" : "border-line-strong bg-sheet hover:border-ink")}>{t.title}</button>
                ))}
              </div>
            )}>
            {plan && <p className="mb-3"><strong>Plan {plan.rank}, proposed:</strong> {plan.summary}</p>}
            <MaterialFlow weeks={weeks} effectiveWeek={plan?.effective_week ?? change.effective_week} useUpEnd={change.use_up_end_week} oldRevision={change.old_revision} newRevision={change.new_revision}
              orders={plan ? [] : inv.purchase_orders} oldMaterial={change.part_number} />
          </Section>

          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Unmet demand" tone={shortage ? "critical" : "done"} value={units(shortage)} detail={short.length ? weekRange(short.map((w) => w.week)) : "No short week"} />
            <Metric label="Excess value" tone={excess ? "pending" : "done"} value={inr(excess)} detail={plan ? "With this plan" : `${inr(inv.excess?.rev_b_scrap_value)} ${change.old_revision}, ${inr(inv.excess?.rev_c_excess_value)} ${change.new_revision}`} />
            <Metric label={`${change.old_revision} at the end`} value={qty(last?.rev_b_closing)} detail={`Closing stock in W${last?.week}`} />
            <Metric label={`${change.new_revision} at the end`} value={qty(last?.rev_c_closing)} detail={`Closing stock in W${last?.week}`} />
          </div>

          {!plan && inv.material_balance && (
            <Section title={`Where ${change.old_revision} supply goes`} note="Opening stock plus open orders, split by what happens to it.">
              <BalanceBar balance={inv.material_balance} revision={change.old_revision} />
            </Section>
          )}

          <div className="grid gap-12 xl:grid-cols-2">
            <Section title="How demand is covered"><DemandCoverage weeks={weeks} oldRevision={change.old_revision} newRevision={change.new_revision} /></Section>
            <Section title="Closing stock and safety stock"><StockBalance weeks={weeks} oldRevision={change.old_revision} newRevision={change.new_revision} /></Section>
          </div>

          <Section title="Weekly records" note="Unmet demand is recorded beside the stock. Stock itself is never negative.">
            <Tabs label="Weekly records" tabs={[
              { id: "b", title: change.old_revision, content: <RevisionTable weeks={weeks} rev="b" name={change.old_revision} /> },
              { id: "c", title: change.new_revision, content: <RevisionTable weeks={weeks} rev="c" name={change.new_revision} /> },
              { id: "d", title: "Demand", content: (
                <TableFrame label="Demand and unmet demand by week">
                  <thead><tr><th>Week</th><th>Demand</th><th>{change.old_revision} used</th><th>{change.new_revision} used</th><th>Unmet</th></tr></thead>
                  <tbody>{weeks.map((w) => <tr key={w.week} className="num"><td className="mono">{week(w.week)}</td><td>{qty(w.demand)}</td><td>{qty(w.rev_b_usage)}</td><td>{qty(w.rev_c_usage)}</td><td className={w.shortage ? "font-semibold text-critical" : ""}>{qty(w.shortage)}</td></tr>)}</tbody>
                </TableFrame>) },
              { id: "o", title: "Orders and stock", content: (
                <div className="space-y-6">
                  <TableFrame label="Purchase orders">
                    <thead><tr><th>Order</th><th>Material</th><th>Supplier</th><th>Quantity</th><th>Ordered</th><th>Arrives</th><th>Status</th><th>Can change until</th></tr></thead>
                    <tbody>{inv.purchase_orders.map((p) => <tr key={p.po_id} className="num"><td className="mono">{p.po_id}</td><td className="mono">{p.material_id}</td><td>{p.supplier_id}, {p.supplier_name} {p.supplier_status !== "Approved" && <Status tone="critical">{p.supplier_status}</Status>}</td><td>{qty(p.quantity)}</td><td className="mono">{week(p.order_week)}</td><td className="mono">{week(p.arrival_week)}</td><td>{p.status}</td><td className="mono">{week(p.change_deadline_week)}</td></tr>)}</tbody>
                  </TableFrame>
                  <TableFrame label="Stock records">
                    <thead><tr><th>Material</th><th>On hand</th><th>Reserved</th><th>Safety stock</th><th>Counted on</th></tr></thead>
                    <tbody>{inv.stock.map((s) => <tr key={s.material_id} className="num"><td className="mono">{s.material_id}</td><td>{qty(s.on_hand)}</td><td>{qty(s.reserved)}</td><td>{qty(s.safety_stock)}</td><td>{s.inventory_date}</td></tr>)}</tbody>
                  </TableFrame>
                </div>) },
            ]} />
          </Section>
        </div>
      )}
    </>
  );
}

function RevisionTable({ weeks, rev, name }: { weeks: Week[]; rev: "b" | "c"; name: string }) {
  const v = (w: Week, key: string) => w[`rev_${rev}_${key}` as keyof Week] as number;
  return (
    <TableFrame label={`${name} by week`}>
      <thead><tr>{["Week", "Opening", "Receipts", "Reserved", "Available", "Safety stock", "Usable", "Used", "Closing"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{weeks.map((w) => (
        <tr key={w.week} className="num"><td className="mono">{week(w.week)}</td>{["opening", "receipts", "reserved", "available", "safety_stock", "usable", "usage", "closing"].map((k) => <td key={k} className={k === "closing" ? "font-semibold" : ""}>{qty(v(w, k))}</td>)}</tr>
      ))}</tbody>
    </TableFrame>
  );
}
