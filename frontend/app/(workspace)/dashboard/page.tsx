"use client";
import Link from "next/link";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { RevisionRibbon } from "@/components/engineering/RevisionRibbon";
import { StageTrack } from "@/components/engineering/StageTrack";
import { SeverityRail } from "@/components/exceptions/SeverityRail";
import { MaterialFlow } from "@/components/inventory/MaterialFlow";
import { useWorkspace } from "@/components/layout/Workspace";
import { DecisionPanel } from "@/components/optimization/DecisionPanel";
import { Empty, LinkButton, Loaded, Metric, Section, Status, toneOf } from "@/components/ui/primitives";
import { api, type Overview } from "@/lib/api";
import { dateTime, inr, qty, units, weekRange, words } from "@/lib/format";
import { useData } from "@/lib/hooks";
import { nextStep } from "@/lib/workflow";

export default function Dashboard() {
  const { change, scenario } = useWorkspace();
  const { data, error, mutate } = useData(["overview", change.change_id, scenario], () => api.overview(change.change_id, scenario));
  return <Loaded data={data} error={error} retry={() => void mutate()}>{(o) => <Board o={o} />}</Loaded>;
}

function headline(o: Overview) {
  const short = o.inventory.weeks.filter((w) => w.shortage > 0);
  if (!o.inventory.weeks.length) return "Inventory cannot be simulated until the records are corrected.";
  if (short.length) return `${units(o.inventory.total_shortage_units)} of demand cannot be met in ${weekRange(short.map((w) => w.week))}.`;
  return "Production is covered in every week of the horizon.";
}

function Board({ o }: { o: Overview }) {
  const { can } = useWorkspace();
  const { inventory: inv, change } = o;
  const step = nextStep(o);
  const critical = o.exceptions.filter((e) => e.severity_level === "CRITICAL" && e.status !== "RESOLVED").length;
  const scrap = inv.excess?.rev_b_scrap_units ?? 0;
  const open = o.actions.filter((a) => a.status !== "DONE");
  return (
    <div className="space-y-12">
      <div className="grid gap-x-12 gap-y-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div>
          <p className="mb-3 text-ink-2">{change.change_id}, {inv.materials[0]?.name ?? change.part_number}: {change.reason}</p>
          <h1 className="display max-w-4xl text-[36px] sm:text-[48px]">
            {headline(o)} {inv.excess_value ? <span className="text-ink-2">Without action, {inr(inv.excess_value)} of stock becomes excess.</span> : null}
          </h1>
          <div className="mt-6"><StageTrack done={o.stage} /></div>
        </div>
        <aside aria-label="What happens next" className="self-end border-l-4 border-tech bg-sheet p-5">
          <p className="display text-2xl">{step.title}</p>
          <p className="mt-1 mb-4 text-ink-2">{step.detail}</p>
          {can(step.permission) ? <LinkButton kind="primary" href={step.href} icon="arrow">{step.label}</LinkButton>
            : <p className="text-sm text-ink-3">Your role can follow this, another role acts on it.</p>}
        </aside>
      </div>

      <Section title="Material flow" note={`W1 to W${inv.horizon_weeks}, without corrective action. Simulation ${inv.simulation_id}, engine ${inv.engine_version}.`}
        action={<LinkButton href="/inventory" kind="quiet" icon="arrow">Inventory monitor</LinkButton>}>
        {inv.weeks.length ? (
          <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_300px]">
            <MaterialFlow weeks={inv.weeks} effectiveWeek={inv.effective_week ?? change.effective_week} useUpEnd={inv.use_up_end_week ?? change.use_up_end_week}
              oldRevision={change.old_revision} newRevision={change.new_revision} orders={inv.purchase_orders} oldMaterial={change.part_number} />
            <div className="grid content-start gap-6 sm:grid-cols-2 xl:grid-cols-1">
              <Metric size="lg" label="Unmet demand" tone={inv.total_shortage_units ? "critical" : "done"} value={units(inv.total_shortage_units)}
                detail={inv.total_shortage_units ? "Over the planning horizon" : "No week is short"} />
              <Metric size="lg" label="Excess inventory exposure" tone={inv.excess_value ? "pending" : "done"} value={inr(inv.excess_value)}
                detail={scrap ? `${qty(scrap)} ${change.old_revision} units left after W${change.use_up_end_week}` : "Nothing left over"} />
              <Metric label="Finished products affected" value={o.finished_products.length} detail={<span className="mono">{o.finished_products.join(", ")}</span>} />
              <Metric label="Waiting for approval" value={o.pending_approvals} tone={o.pending_approvals ? "pending" : undefined}
                detail={<Link href="/approvals" className="text-tech hover:underline">All changes</Link>} />
            </div>
          </div>
        ) : <Empty title="No simulation">{inv.issues[0]?.description}</Empty>}
      </Section>

      <div className="grid gap-12 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Section title="Proposed plan" note={o.run ? `Run ${o.run.run_id}, ${dateTime(o.run.created_at)}` : undefined}>
          {o.run ? <DecisionPanel run={o.run} action={!o.run.approval && o.run.recommendations.length > 0 && can("DECIDE_PLAN") && !o.run.stale
            ? <LinkButton kind="primary" href={`/approvals/${o.run.run_id}`} icon="arrow">Review and decide</LinkButton> : <LinkButton href="/optimization" icon="arrow">Open the optimization</LinkButton>} />
            : <Empty title="Not planned yet">The optimization runs after the ECN is confirmed.</Empty>}
        </Section>
        <Section title="Exceptions" note={critical ? `${critical} critical, worst first` : "Worst first"} action={<LinkButton href="/exceptions" kind="quiet" icon="arrow">All</LinkButton>}>
          {o.exceptions.length ? <SeverityRail items={o.exceptions.slice(0, 4)} compact /> : <Empty title="No exception" />}
        </Section>
      </div>

      <div className="grid gap-12 lg:grid-cols-2 xl:grid-cols-3">
        <Section title="Revision handover" className="xl:col-span-1">
          <RevisionRibbon from={change.old_revision} to={change.new_revision} effectiveWeek={change.effective_week} useUpEnd={change.use_up_end_week} horizon={inv.horizon_weeks} interchangeable={change.interchangeability} />
          <div className="mt-5 flex flex-wrap gap-2">
            <Status tone={toneOf(o.validation.status)}>Records {words(o.validation.status).toLowerCase()}</Status>
            <Status tone={toneOf(change.approval_status)}>ECN {change.approval_status.toLowerCase()}</Status>
          </div>
        </Section>
        <Section title="Open actions" action={<LinkButton href="/actions" kind="quiet" icon="arrow">Tracker</LinkButton>}>
          {open.length ? (
            <ul className="divide-y divide-line border-y border-line">
              {open.slice(0, 5).map((a) => (
                <li key={a.action_id} className="flex items-center justify-between gap-3 py-2.5">
                  <span><span className="font-semibold">{a.summary}</span><span className="block text-sm text-ink-2">{a.owner_role}{a.assignee && `, ${a.assignee}`}{a.due_week && `, due W${a.due_week}`}</span></span>
                  <Status tone={toneOf(a.status)}>{words(a.status)}</Status>
                </li>
              ))}
            </ul>
          ) : <p className="text-ink-2">{o.run?.approval?.decision === "APPROVED" ? "Every approved action is done." : "Actions appear after a planner approves a plan."}</p>}
        </Section>
        <Section title="Recent decisions">
          {o.recent_events.length ? <AuditTimeline events={o.recent_events} compact /> : <p className="text-ink-2">{can("VIEW_AUDIT") ? "Nothing has been recorded yet." : "Your role does not include the audit history."}</p>}
        </Section>
      </div>
    </div>
  );
}
