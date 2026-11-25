"use client";
import { useState, type FormEvent } from "react";
import { ExplanationPanel } from "@/components/ai/ExplanationPanel";
import { MaterialFlow } from "@/components/inventory/MaterialFlow";
import { useWorkspace } from "@/components/layout/Workspace";
import { RobustnessMatrix } from "@/components/optimization/RobustnessMatrix";
import { Icon } from "@/components/ui/icons";
import { Alert, Button, Empty, ErrorNote, LinkButton, Loaded, PageHeading, Section, Status, TableFrame, Textarea, cx } from "@/components/ui/primitives";
import { api, type Run, type WhatIfParameters, type WhatIfParsed, type WhatIfResult } from "@/lib/api";
import { dateTime, inr, qty, signed, week, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

const EXAMPLES = [
  "What if the Rev C supplier is delayed by one week and demand increases by 10%?",
  "What if demand drops by 10%?",
  "What if supplier S2 is blocked?",
  "What if the change becomes effective in W7?",
];

function described(p: WhatIfParameters): [string, string, boolean][] {
  const change = p.po_quantity_change;
  return [
    ["Rev C delivery", p.lead_time_delta ? `${p.lead_time_delta} wk later` : "as planned", !!p.lead_time_delta],
    ["Demand", p.demand_change_percent ? `${p.demand_change_percent > 0 ? "+" : "−"}${Math.abs(p.demand_change_percent)}%` : "as planned", !!p.demand_change_percent],
    ["Effective week", p.effective_week ? week(p.effective_week) : "engine decides", !!p.effective_week],
    ["Order change", change ? `${change.po_id}: ${change.quantity_delta}` : "none", !!change],
    ["Blocked supplier", p.supplier_block ?? "none", !!p.supplier_block],
  ];
}

export default function WhatIfPage() {
  const { change, scenario } = useWorkspace();
  const { data, error, mutate } = useData(["overview", change.change_id, scenario], () => api.overview(change.change_id, scenario));
  return (
    <>
      <PageHeading title="What-if simulator" lead="Ask what happens if something changes. The question is translated into parameters, you confirm them, and the engine plans again on a copy. The current plan is never touched." />
      <Loaded data={data} error={error} retry={() => void mutate()}>
        {(o) => o.run ? <Simulator key={o.run.run_id} run={o.run} oldRevision={o.change.old_revision} newRevision={o.change.new_revision} useUpEnd={o.change.use_up_end_week} />
          : <Empty title="There is no plan to compare with" action={<LinkButton href="/ecn" kind="primary">ECN intake</LinkButton>}>Run the optimization first. Its result becomes the baseline.</Empty>}
      </Loaded>
    </>
  );
}

type Names = { oldRevision: string; newRevision: string; useUpEnd: number };

function Simulator({ run, ...names }: { run: Run } & Names) {
  const { can } = useWorkspace();
  const { run: act, pending, error, clear } = useAction();
  const [question, setQuestion] = useState("");
  const [parsed, setParsed] = useState<WhatIfParsed | null>(null);
  const [shown, setShown] = useState<string | null>(null);
  const history = useData(["what-ifs", run.run_id], () => api.whatIfs(run.run_id));
  const result = useData(shown ? ["what-if", shown] : null, () => api.whatIf(shown!));

  const ask = async (e: FormEvent) => {
    e.preventDefault();
    setShown(null);
    setParsed(null);
    const reading = await act("parse", () => api.parseWhatIf(run.run_id, question));
    if (reading) setParsed(reading);
  };
  const confirm = async () => {
    const outcome = await act("run", () => api.confirmWhatIf(run.run_id, parsed!.question, parsed!.parameters!));
    if (outcome) setShown(outcome.scenario_id);
  };
  const reset = () => { setParsed(null); setShown(null); setQuestion(""); clear(); };
  const best = run.recommendations[0];

  return (
    <div className="space-y-12">
      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {can("RUN_WHAT_IF") ? (
            <form onSubmit={ask} className="space-y-3">
              <Textarea label="What if" rows={2} maxLength={500} required value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={EXAMPLES[0]} />
              <div className="flex flex-wrap gap-2">
                <Button type="submit" kind="primary" busy={pending === "parse"} disabled={!question.trim()}>Interpret</Button>
                {(parsed || shown) && <Button icon="replay" onClick={reset}>Back to the baseline</Button>}
              </div>
              <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm">{EXAMPLES.map((x) => <button key={x} type="button" onClick={() => setQuestion(x)} className="text-left text-tech hover:underline">{x}</button>)}</p>
            </form>
          ) : <Alert>Your role can read scenarios. Planning, engineering and purchasing run them.</Alert>}
          {error && <ErrorNote error={error} />}
          {parsed && parsed.status !== "OK" && (
            <Alert kind="warning" title={parsed.status === "NEEDS_CLARIFICATION" ? "One detail is missing" : parsed.status === "INVALID_PARAMETER" ? "That value is outside the limits" : "Not something this simulator changes"}>{parsed.message}</Alert>
          )}
          {parsed?.parameters && !shown && (
            <div className="animate-enter border border-ink bg-sheet">
              <p className="border-b border-line px-5 py-3 text-sm text-ink-2">Read by {parsed.source}{parsed.provider_error && `, because the AI failed (${parsed.provider_error})`}. Check it before it runs.</p>
              <dl className="grid sm:grid-cols-5">
                {described(parsed.parameters).map(([k, v, changed]) => (
                  <div key={k} className={cx("border-line px-5 py-3 not-first:border-t sm:not-first:border-t-0 sm:not-first:border-l", changed && "bg-tech-soft")}><dt className="text-[13px] text-ink-2">{k}</dt><dd className={cx("font-semibold", !changed && "font-normal text-ink-3")}>{v}</dd></div>
                ))}
              </dl>
              <div className="border-t border-line px-5 py-4"><Button kind="primary" icon="check" busy={pending === "run"} onClick={confirm}>{pending === "run" ? "Planning the scenario" : "Confirm and run"}</Button></div>
            </div>
          )}
        </div>
        <aside className="space-y-6">
          <Section title="Baseline">
            {best ? <><p className="font-semibold">{best.summary}</p><p className="num text-ink-2">{qty(best.shortage_units)} short, {inr(best.secondary_cost)} E + C, robust {best.robustness?.display}</p></> : <p>{words(run.decision)}</p>}
          </Section>
          <Section title="Earlier scenarios">
            {history.data?.length ? <ul className="space-y-1">{history.data.map((h) => (
              <li key={h.scenario_id}><button type="button" aria-pressed={shown === h.scenario_id} onClick={() => setShown(h.scenario_id)} className={cx("w-full border-l-2 px-3 py-1.5 text-left hover:bg-sunken", shown === h.scenario_id ? "border-tech bg-tech-soft" : "border-line-strong")}>{h.question || h.scenario_id}<span className="block text-[13px] text-ink-3">{dateTime(h.created_at)}, {h.created_by}</span></button></li>
            ))}</ul> : <p className="text-ink-2">None for this run.</p>}
          </Section>
        </aside>
      </div>
      {shown && <Loaded data={result.data} error={result.error}>{(r) => <Outcome r={r} {...names} />}</Loaded>}
    </div>
  );
}

const MEASURE: Record<string, string> = { decision: "Decision", plan: "Best plan", shortage_units: "Unmet demand", excess_value: "Excess value", action_cost: "Action cost", secondary_cost: "Excess plus action cost", robustness: "Stress runs covered" };

function Outcome({ r, oldRevision, newRevision, useUpEnd }: { r: WhatIfResult } & Names) {
  const money = (m: string) => ["excess_value", "action_cost", "secondary_cost"].includes(m);
  const show = (m: string, v: unknown) => v == null ? "No plan" : typeof v === "number" ? (money(m) ? inr(v) : qty(v)) : m === "decision" ? words(String(v)) : String(v);
  const plans = [["Baseline", r.base_plan], ["Scenario", r.alternative_plan]] as const;
  return (
    <div className="animate-enter space-y-12">
      <Section title="What changes" note={r.question}>
        <p className="display mb-5 max-w-4xl text-2xl">{r.description}</p>
        <TableFrame label="Baseline and scenario">
          <thead><tr><th>Measure</th><th>Baseline</th><th>Scenario</th><th>Difference</th></tr></thead>
          <tbody>{r.comparison.map((c) => (
            <tr key={c.measure} className="num"><td className="font-semibold">{MEASURE[c.measure] ?? words(c.measure)}</td><td>{show(c.measure, c.base)}</td>
              <td className={cx(c.measure === "shortage_units" && Number(c.alternative) > 0 && "font-semibold text-critical")}>{show(c.measure, c.alternative)}</td>
              <td>{c.change == null ? "" : c.change === 0 ? <span className="text-ink-3">no change</span> : <span className={cx("inline-flex items-center gap-1 font-semibold", c.change > 0 ? "text-critical" : "text-done")}><Icon name={c.change > 0 ? "alert" : "check"} size={14} />{signed(c.change, money(c.measure) ? inr : qty)}</span>}</td></tr>
          ))}</tbody>
        </TableFrame>
        {r.constrained && <p className="mt-3 text-sm text-ink-2">The scenario is the best plan that contains what you asked for, not a free optimum.</p>}
        <div className="mt-4 space-y-2">{r.escalations.map((e) => <Alert key={e.code} kind="warning" title={words(e.code)}>{e.message}</Alert>)}</div>
      </Section>
      <div className="grid gap-10 2xl:grid-cols-2">
        {plans.map(([name, p]) => (
          <Section key={name} title={name} note={p?.summary}>
            {p ? <MaterialFlow weeks={p.weekly} oldRevision={oldRevision} newRevision={newRevision} useUpEnd={useUpEnd} effectiveWeek={effective(p.weekly, useUpEnd)} /> : <Empty title="No plan is recommended" />}
          </Section>
        ))}
      </div>
      <div className="grid gap-10 xl:grid-cols-2">
        <Section title="New exceptions" note="Before any corrective action, compared with the baseline records.">
          {r.new_exceptions.length ? <ul className="divide-y divide-line border-y border-line">{r.new_exceptions.map((e) => <li key={e.exception_id} className="py-2.5"><Status tone={e.band === "Critical" ? "critical" : e.band === "High" ? "high" : "pending"}>{e.band}</Status> <span className="font-semibold">{words(e.type)}</span> <span className="mono">{week(e.week)}</span><p className="text-sm text-ink-2">{e.description}</p></li>)}</ul> : <p className="text-ink-2">None.</p>}
        </Section>
        <Section title="Robustness of the scenario plan">
          {r.alternative_plan?.robustness ? <RobustnessMatrix robustness={r.alternative_plan.robustness} caption={r.alternative_plan.summary} /> : <p className="text-ink-2">No plan to stress.</p>}
        </Section>
      </div>
      <Section title="Explanation">
        {r.explanation ? <ExplanationPanel explanation={r.explanation} /> : <p className="max-w-[68ch] border-l-2 border-tech bg-sheet py-2 pl-5"><Status tone="neutral">Template, filled from engine facts</Status><span className="mt-2 block">{r.description}</span></p>}
      </Section>
    </div>
  );
}

/** First week whose applicable revision is C, as the engine reported it. */
function effective(weeks: { week: number; applicable_revision?: string | null }[], useUpEnd: number) {
  return weeks.find((w) => w.applicable_revision === "C")?.week ?? useUpEnd + 1;
}
