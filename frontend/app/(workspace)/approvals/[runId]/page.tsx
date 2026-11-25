"use client";
import Link from "next/link";
import { use, useState } from "react";
import { ExplanationPanel } from "@/components/ai/ExplanationPanel";
import { useWorkspace } from "@/components/layout/Workspace";
import { decisionState } from "@/components/optimization/DecisionPanel";
import { RobustnessMatrix } from "@/components/optimization/RobustnessMatrix";
import { Icon } from "@/components/ui/icons";
import { Confirm } from "@/components/ui/overlay";
import { Alert, Button, ErrorNote, Loaded, PageHeading, Section, Select, Status, Textarea, cx } from "@/components/ui/primitives";
import { api, type EvaluatedPlan, type Menu, type Run } from "@/lib/api";
import { dateTime, inr, qty, week, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

export default function ApprovalPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  const { data, error, mutate } = useData(["run", runId], () => api.run(runId));
  return <Loaded data={data} error={error} retry={() => void mutate()}>{(run) => <Case key={run.run_id} run={run} />}</Loaded>;
}

type Choice = { kind: "APPROVED" | "REJECTED"; plan?: string; modified?: EvaluatedPlan };

function Case({ run }: { run: Run }) {
  const { can } = useWorkspace();
  const state = decisionState(run);
  const [plan, setPlan] = useState(run.recommended_plan_id ?? "");
  const [modified, setModified] = useState<EvaluatedPlan | null>(null);
  const chosen = run.recommendations.find((p) => p.plan_id === plan);
  const explanation = useData(["explanation", run.run_id], () => api.explanation(run.run_id));
  const rejected = useData(["rejected", run.run_id], () => api.rejected(run.run_id));
  const open = !run.approval && !run.stale && run.newest && run.decision !== "INVALID_DATA";
  return (
    <>
      <PageHeading title="Decide on the proposal" lead={<>{run.change_id}, run <span className="mono">{run.run_id}</span>, planned {dateTime(run.created_at)}. Read the evidence, then decide on the right.</>} action={<Status tone={state.tone}>{state.text}</Status>} />
      <div className="grid gap-12 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="space-y-12">
          <Section title="Plans you can approve">
            {run.recommendations.length === 0 ? <Alert kind="critical">{run.escalations[0]?.message ?? "There is no plan to approve."}</Alert> : (
              <div role="radiogroup" aria-label="Plan" className="space-y-2">
                {run.recommendations.map((p) => (
                  <label key={p.plan_id} className={cx("grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] gap-x-4 border bg-sheet px-5 py-4", plan === p.plan_id ? "border-2 border-tech" : "border-line-strong hover:border-ink")}>
                    <input type="radio" name="plan" value={p.plan_id} checked={plan === p.plan_id} disabled={!open} onChange={() => setPlan(p.plan_id)} className="mt-1.5 size-4 accent-tech" />
                    <span>
                      <span className="flex flex-wrap items-baseline justify-between gap-x-4"><span className="display text-[22px]">{p.rank}. {p.summary}</span><span className="num font-semibold">{inr(p.secondary_cost)}</span></span>
                      <span className="num block text-sm text-ink-2">{qty(p.shortage_units)} short, {inr(p.excess_value)} excess, {inr(p.action_cost)} fees, effective {week(p.effective_week)}, stress runs covered {p.robustness?.display}</span>
                    </span>
                  </label>
                ))}
              </div>
            )}
            <div className="mt-4 space-y-2">{run.escalations.map((e) => <Alert key={e.code} kind="warning" title={words(e.code)}>{e.message}</Alert>)}</div>
          </Section>

          <Section title="Hard rules" note="Every approvable plan passes all of them. The count shows what the engine refused.">
            <ul className="grid gap-x-8 sm:grid-cols-2">
              {run.hard_rules.map((r) => <li key={r.rule} className="flex items-start gap-2 border-b border-line py-2"><Icon name="check" size={16} className="mt-1 text-done" /><span className="flex-1">{r.title}</span>{r.violations > 0 && <span className="num text-sm text-ink-3">{r.violations} refused</span>}</li>)}
            </ul>
            {rejected.data && rejected.data.total > 0 && (
              <details className="mt-3 text-sm"><summary className="font-semibold text-tech">Rejected alternatives ({rejected.data.total})</summary>
                <ul className="mt-2 space-y-1.5">{rejected.data.items.map((p) => <li key={p.plan_id}><strong>{p.summary}.</strong> {p.rejection_reasons.map((r) => r.description).join(" ")}</li>)}</ul></details>
            )}
          </Section>

          {chosen?.robustness && <Section title="Stress runs of the selected plan"><div className="max-w-2xl"><RobustnessMatrix robustness={chosen.robustness} caption={chosen.summary} /></div></Section>}
          <Section title="Explanation"><Loaded data={explanation.data} error={explanation.error}>{(e) => e ? <ExplanationPanel explanation={e} /> : <p>No explanation is stored.</p>}</Loaded></Section>
          {open && can("DECIDE_PLAN") && <Modify run={run} result={modified} onResult={setModified} />}
        </div>
        <aside className="xl:sticky xl:top-44 xl:self-start">
          <Decision run={run} open={open} plan={plan} planSummary={chosen?.summary} modified={modified} />
        </aside>
      </div>
    </>
  );
}

function Decision({ run, open, plan, planSummary, modified }: { run: Run; open: boolean; plan: string; planSummary?: string; modified: EvaluatedPlan | null }) {
  const { can } = useWorkspace();
  const { run: act, pending, error } = useAction();
  const [comment, setComment] = useState("");
  const [asking, setAsking] = useState<Choice | null>(null);
  if (run.approval) {
    const a = run.approval;
    return (
      <Section title={a.decision === "APPROVED" ? "Approved" : "Rejected"}>
        <p className="font-semibold">{a.plan_summary ?? "No plan"}</p>
        {a.modified && <p className="text-sm text-ink-2">Modified by the planner</p>}
        <p className="mt-2 border-l-2 border-line-strong pl-3">{a.comment || "No comment"}</p>
        <p className="mt-2 text-sm text-ink-2">{a.user_name} ({a.role}), {dateTime(a.created_at)}{a.closed_at && `. Closed ${dateTime(a.closed_at)}`}</p>
        {a.decision === "APPROVED" && <p className="mt-4"><Link href="/actions" className="font-semibold text-tech hover:underline">Follow the actions</Link></p>}
      </Section>
    );
  }
  if (!can("DECIDE_PLAN")) return <Section title="Decision"><Alert>Only a production planner decides. You can read the case.</Alert></Section>;
  if (!open) return <Section title="Decision"><Alert kind="warning">{run.stale ? "The planning records changed after this run. Plan again before deciding." : !run.newest ? "A newer run exists. Decide on that one." : "There is nothing to decide."}</Alert></Section>;

  // Mirrors the backend rule so the planner learns it before submitting; the backend enforces it.
  const why = plan !== run.recommended_plan_id ? "It is not the leading plan." : run.requires_planner_review ? "The case is escalated." : null;
  const missing = !comment.trim();
  const submit = async () => {
    const done = await act("decide", () => api.decide(run.run_id, {
      decision: asking!.kind, comment, plan_id: asking!.kind === "APPROVED" && !asking!.modified ? plan : null,
      modified_actions: asking!.modified ? asking!.modified.actions as { action: string }[] : null,
    }));
    if (done) setAsking(null);
  };
  return (
    <Section title="Decision">
      <Textarea label="Comment" rows={4} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} hint={why ? `Needed to approve. ${why} Always needed to reject.` : "Needed to reject or to approve a modified plan."} />
      <div className="mt-4 space-y-2">
        <Button kind="primary" icon="check" className="w-full" disabled={!plan || (!!why && missing)} onClick={() => setAsking({ kind: "APPROVED", plan })}>Approve plan</Button>
        {modified?.feasibility === "FEASIBLE" && <Button kind="dark" icon="edit" className="w-full" disabled={missing} onClick={() => setAsking({ kind: "APPROVED", modified })}>Approve modified plan</Button>}
        <Button kind="danger" icon="cross" className="w-full" disabled={missing} onClick={() => setAsking({ kind: "REJECTED" })}>Reject</Button>
      </div>
      <p className="mt-3 text-sm text-ink-3">The decision is final for this run and is written to the audit history under your name.</p>
      <Confirm open={!!asking} onClose={() => setAsking(null)} onConfirm={submit} busy={pending === "decide"} danger={asking?.kind === "REJECTED"}
        title={asking?.kind === "REJECTED" ? "Reject the proposal?" : "Approve this plan?"} action={asking?.kind === "REJECTED" ? "Reject" : "Approve"}>
        {error && <div className="mb-3"><ErrorNote error={error} /></div>}
        <p>{asking?.kind === "REJECTED" ? "No action is created. A new run is needed for another decision." : <><strong>{asking?.modified?.summary ?? planSummary}</strong>. Its actions go to the responsible teams.</>}</p>
      </Confirm>
    </Section>
  );
}

function Modify({ run, result, onResult }: { run: Run; result: EvaluatedPlan | null; onResult: (plan: EvaluatedPlan | null) => void }) {
  const { data } = useData(["menus", run.run_id], () => api.menus(run.run_id));
  const { run: act, pending, error } = useAction();
  const [picks, setPicks] = useState<Record<string, number>>({});
  if (!data?.length) return null;
  // start from the leading plan: the option whose actions are exactly that plan's actions for this decision
  const leading = (run.recommendations[0]?.actions ?? []).map((a) => JSON.stringify(a));
  const preset = (m: Menu) => {
    const mine = new Set(m.options.flatMap((o) => o.actions.map((a) => JSON.stringify(a))).filter((a) => leading.includes(a)));
    return Math.max(0, m.options.findIndex((o) => o.actions.length === mine.size && o.actions.every((a) => mine.has(JSON.stringify(a)))));
  };
  const pick = (m: Menu) => picks[m.name] ?? preset(m);
  const evaluate = async () => {
    const actions = data.flatMap((m) => m.options[pick(m)]!.actions) as { action: string }[];
    const plan = await act("evaluate", () => api.evaluate(run.run_id, actions));
    if (plan) onResult(plan);
  };
  return (
    <Section title="Modify the plan" note="Choose one permitted option for each decision. The engine evaluates the combination before it can be approved.">
      <div className="grid gap-4 sm:grid-cols-2">
        {data.map((m) => (
          <Select key={m.name} label={m.name} value={pick(m)} onChange={(e) => { setPicks((p) => ({ ...p, [m.name]: Number(e.target.value) })); onResult(null); }}>
            {m.options.map((o, i) => <option key={o.label} value={i}>{o.label}</option>)}
          </Select>
        ))}
      </div>
      <div className="mt-4"><Button busy={!!pending} onClick={evaluate}>Evaluate this plan</Button></div>
      {error && <div className="mt-4"><ErrorNote error={error} /></div>}
      {result && (
        <div className="mt-4 animate-enter">
          {result.feasibility === "FEASIBLE"
            ? <Alert kind="done" title={result.summary}><span className="num">{qty(result.shortage_units)} short, {inr(result.excess_value)} excess, {inr(result.action_cost)} fees, {inr(result.secondary_cost)} in total. Stress runs covered {result.robustness?.display}.</span></Alert>
            : <Alert kind="critical" title="Breaks a hard rule">{result.rejection_reasons.map((r) => <p key={r.code + r.description}>{r.description}</p>)}</Alert>}
        </div>
      )}
    </Section>
  );
}
