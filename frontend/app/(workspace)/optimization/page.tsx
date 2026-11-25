"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ExplanationPanel } from "@/components/ai/ExplanationPanel";
import { useWorkspace } from "@/components/layout/Workspace";
import { CostBars } from "@/components/optimization/CostBar";
import { DecisionPanel } from "@/components/optimization/DecisionPanel";
import { RobustnessMatrix } from "@/components/optimization/RobustnessMatrix";
import { Icon } from "@/components/ui/icons";
import { Pager, Tabs } from "@/components/ui/overlay";
import { Alert, Button, Empty, ErrorNote, LinkButton, Loaded, PageHeading, Section, Status, TableFrame, cx } from "@/components/ui/primitives";
import { api, type Run } from "@/lib/api";
import { dateTime, inr, qty, week, weekRange, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

export default function OptimizationPage() {
  return <Suspense><Optimization /></Suspense>;
}

function Optimization() {
  const { change, scenario } = useWorkspace();
  const asked = useSearchParams().get("run");
  const overview = useData(asked ? null : ["overview", change.change_id, scenario], () => api.overview(change.change_id, scenario));
  const single = useData(asked ? ["run", asked] : null, () => api.run(asked!));
  const data = asked ? single.data : overview.data && { run: overview.data.run };
  const run = data && ("run" in data ? data.run : data);
  if (data && !run) {
    return (
      <>
        <PageHeading title="Optimization" />
        <Empty title="No planning run for this change and data variant" action={<LinkButton href="/ecn" kind="primary">ECN intake</LinkButton>}>The optimization runs once the ECN is confirmed.</Empty>
      </>
    );
  }
  return <Loaded data={run as Run | undefined} error={single.error ?? overview.error}>{(r) => <Result key={r.run_id} run={r} />}</Loaded>;
}

function Result({ run }: { run: Run }) {
  const { can } = useWorkspace();
  const decided = !!run.approval;
  return (
    <>
      <PageHeading title="Optimization" lead={<>Run <span className="mono">{run.run_id}</span>, {dateTime(run.created_at)} by {run.created_by}. {qty(run.counts.candidates)} candidate plans, {qty(run.counts.feasible)} feasible, in {run.computation_seconds.toFixed(1)} s.</>} />
      <div className="mb-8 space-y-3">
        {run.stale && <Alert kind="warning" title="The planning records changed after this run">It can be read but not approved. Plan again from the ECN review.</Alert>}
        {!run.newest && <Alert kind="warning">A newer run exists for this change.</Alert>}
      </div>
      <div className="space-y-12">
        <DecisionPanel run={run} action={!decided && run.recommendations.length > 0 && !run.stale && run.newest && can("DECIDE_PLAN") && <LinkButton href={`/approvals/${run.run_id}`} kind="primary" icon="arrow">Review and decide</LinkButton>} />
        <Tabs label="Evidence" tabs={[
          { id: "why", title: "Explanation", content: <Explanation run={run} /> },
          { id: "plans", title: "Plans", content: <Plans run={run} /> },
          { id: "rules", title: `Rejected (${run.counts.rejected})`, content: <Rejected run={run} /> },
          { id: "robust", title: "Robustness", content: <Robust run={run} /> },
          { id: "base", title: "Baselines", content: <Baselines run={run} /> },
          { id: "trace", title: "Run record", content: <Trace run={run} /> },
        ]} />
      </div>
    </>
  );
}

function Explanation({ run }: { run: Run }) {
  const { can } = useWorkspace();
  const { run: act, pending, error } = useAction();
  const { data, error: problem, mutate } = useData(["explanation", run.run_id], () => api.explanation(run.run_id));
  return (
    <Section title="What the result says" action={can("RUN_PLANNING") && <Button icon="replay" busy={!!pending} onClick={() => act("explain", () => api.explain(run.run_id))}>Explain again</Button>}>
      {error && <ErrorNote error={error} />}
      <Loaded data={data} error={problem} retry={() => void mutate()}>{(e) => e ? <ExplanationPanel explanation={e} /> : <Empty title="No explanation stored" />}</Loaded>
    </Section>
  );
}

function Plans({ run }: { run: Run }) {
  const [offset, setOffset] = useState(0);
  const { data, error } = useData(["plans", run.run_id, offset], () => api.plans(run.run_id, 12, offset));
  if (!run.recommendations.length) return <Empty title="No feasible plan to compare" />;
  return (
    <div className="space-y-12">
      <Section title="Top three" note="Ranked by unmet demand first, then by excess plus action cost. Nothing else changes the order.">
        <CostBars rows={run.recommendations.map((p) => ({ name: `${p.rank}. ${p.summary}`, detail: `${qty(p.shortage_units)} short, robust ${p.robustness?.display ?? "–"}`, excess: p.excess_value, action: p.action_cost, total: p.secondary_cost, emphasis: p.rank === 1 }))} />
        {run.near_ties.length > 0 && (
          <div className="mt-6"><Alert kind="warning" title="Near-tie">
            {run.near_ties.length === 1 ? "One plan costs" : `${run.near_ties.length} plans cost`} almost the same as the leader (within {inr(Math.max(...run.near_ties.map((t) => t.absolute)))}). The engine does not choose between them; the planner does.
          </Alert></div>
        )}
      </Section>
      <Section title="Best plan for each effective week">
        <TableFrame label="Best plan by effective week">
          <thead><tr><th>Effective week</th><th>Plan</th><th>Unmet</th><th>Excess</th><th>Action cost</th><th>E + C</th></tr></thead>
          <tbody>{run.effective_week_comparison.map((c) => <tr key={c.effective_week} className="num"><td className="mono">{week(c.effective_week)}</td><td>{c.summary ?? "No feasible plan"}</td><td>{qty(c.shortage_units)}</td><td>{inr(c.excess_value)}</td><td>{inr(c.action_cost)}</td><td className="font-semibold">{inr(c.secondary_cost)}</td></tr>)}</tbody>
        </TableFrame>
      </Section>
      <Section title={`All feasible plans (${qty(run.counts.feasible)})`}>
        <Loaded data={data} error={error}>{(page) => (
          <>
            <TableFrame label="Ranked feasible plans">
              <thead><tr><th>Rank</th><th>Plan</th><th>Actions</th><th>Effective</th><th>Unmet</th><th>Excess</th><th>Action cost</th><th>E + C</th></tr></thead>
              <tbody>{page.items.map((p) => (
                <tr key={p.plan_id} className="num"><td>{p.rank}</td><td className="mono whitespace-nowrap">{p.plan_id}</td><td className="min-w-64">{p.summary}{p.redundant_of && <span className="block text-[13px] text-ink-3">Same result as {p.redundant_of} with more actions</span>}</td><td className="mono">{week(p.effective_week)}</td><td>{qty(p.shortage_units)}</td><td>{inr(p.excess_value)}</td><td>{inr(p.action_cost)}</td><td className="font-semibold">{inr(p.secondary_cost)}</td></tr>
              ))}</tbody>
            </TableFrame>
            <Pager total={page.total} limit={12} offset={offset} onChange={setOffset} />
          </>
        )}</Loaded>
      </Section>
    </div>
  );
}

function Rejected({ run }: { run: Run }) {
  const { data, error } = useData(["rejected", run.run_id], () => api.rejected(run.run_id));
  return (
    <div className="grid gap-12 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <Section title="Seven hard rules" note="A plan that breaks one is rejected before it is simulated, whatever it would cost.">
        <ul className="divide-y divide-line border-y border-line bg-sheet">
          {run.hard_rules.map((r) => (
            <li key={r.rule} className="flex items-center justify-between gap-4 px-4 py-2.5">
              <span>{r.title}</span>
              {r.violations ? <Status tone="critical">{r.violations} rejected</Status> : <span className="flex items-center gap-1 text-sm text-ink-3"><Icon name="check" size={14} />No violation</span>}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Rejected candidates">
        <Loaded data={data} error={error}>{(list) => list.items.length ? (
          <ul className="space-y-3">{list.items.map((p) => (
            <li key={p.plan_id} className="border-l-4 border-critical bg-sheet px-4 py-3">
              <p className="flex flex-wrap items-baseline gap-x-3"><span className="font-semibold">{p.summary}</span><span className="mono text-[13px] text-ink-3">{p.plan_id}</span></p>
              <ul className="mt-1 text-sm text-ink-2">{p.rejection_reasons.map((r) => <li key={r.code + r.description}>{words(r.rule)}: {r.description}</li>)}</ul>
            </li>
          ))}</ul>
        ) : <Empty title="No plan was rejected" />}</Loaded>
      </Section>
    </div>
  );
}

function Robust({ run }: { run: Run }) {
  if (!run.recommendations.length) return <Empty title="No plan to stress" />;
  return (
    <Section title="Nine stress runs" note="Rev C up to two weeks late, demand ten percent lower and higher. Supplementary evidence; it never changes the ranking.">
      <div className="grid gap-10 lg:grid-cols-2 2xl:grid-cols-3">
        {run.recommendations.map((p) => p.robustness && <RobustnessMatrix key={p.plan_id} robustness={p.robustness} caption={`Plan ${p.rank}: ${p.summary}`} />)}
      </div>
    </Section>
  );
}

const CONFIG: Record<string, string> = { BASELINE_A: "Baseline A, no action", BASELINE_B: "Baseline B, use up Rev B first", CHANGEWISE: "Proposed plan" };

function Baselines({ run }: { run: Run }) {
  const { data, error } = useData(["comparison", run.run_id], () => api.comparison(run.run_id));
  return (
    <Section title="Compared with doing nothing and with a simple run-out" note="Same records, same simulator. Synthetic data: this shows ranking logic, not proven savings.">
      <Loaded data={data} error={error}>{(rows) => rows.length ? (
        <div className="space-y-8">
          <CostBars rows={rows.map((c) => ({ name: CONFIG[c.configuration] ?? c.configuration, detail: c.shortage_units ? `${qty(c.shortage_units)} units short` : "no shortage", excess: c.excess_value, action: c.action_cost, total: c.secondary_cost, emphasis: c.configuration === "CHANGEWISE" }))} />
          <TableFrame label="Baseline comparison">
            <thead><tr><th>Configuration</th><th>Unmet</th><th>Short weeks</th><th>Rev B left</th><th>Rev C closing</th><th>E + C</th><th>Rule violations</th><th>Stress runs covered</th></tr></thead>
            <tbody>{rows.map((c) => <tr key={c.configuration} className="num"><td>{CONFIG[c.configuration] ?? c.configuration}<span className="block text-[13px] text-ink-3">{c.assumptions.join(" ")}</span></td><td className={c.shortage_units ? "font-semibold text-critical" : ""}>{qty(c.shortage_units)}</td><td className="mono">{weekRange(c.shortage_weeks) || "none"}</td><td>{qty(c.rev_b_leftover)}</td><td>{qty(c.rev_c_closing)}</td><td className="font-semibold">{inr(c.secondary_cost)}</td><td>{c.hard_rule_violations}</td><td>{c.robustness.display}</td></tr>)}</tbody>
          </TableFrame>
        </div>
      ) : <Empty title="Not compared">The records are invalid, so no configuration was run.</Empty>}</Loaded>
    </Section>
  );
}

function Trace({ run }: { run: Run }) {
  const rows: [string, string][] = [["Decision", words(run.decision)], ["Method", run.method ?? "Not run"], ["Engine version", run.engine_version], ["Simulator", run.simulator], ["Input hash", run.input_hash], ["Settings hash", run.config_hash], ["ECN review", run.review_id]];
  return (
    <Section title="Run record" note="Enough to repeat this run exactly. The stored snapshot cannot be edited." action={<LinkButton href="/replay" kind="quiet" icon="arrow">Replay</LinkButton>}>
      <dl className="divide-y divide-line border-y border-line bg-sheet">{rows.map(([k, v], i) => <div key={k} className="grid gap-x-4 px-4 py-2 sm:grid-cols-[160px_1fr]"><dt className="text-ink-2">{k}</dt><dd className={cx("break-all", i > 0 && "mono")}>{v}</dd></div>)}</dl>
    </Section>
  );
}
