"use client";
import Link from "next/link";
import { useState } from "react";
import { useWorkspace } from "@/components/layout/Workspace";
import { Pager } from "@/components/ui/overlay";
import { Alert, Button, Empty, ErrorNote, Loaded, PageHeading, Section, Status, TableFrame, toneOf } from "@/components/ui/primitives";
import { api, type Replay } from "@/lib/api";
import { dateTime, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

const VERDICT: Record<Replay["status"], [string, "done" | "critical"]> = {
  MATCHED: ["The stored result was reproduced exactly.", "done"],
  DIFFERENT: ["The result is different: the engine, its settings or the simulator changed since the run.", "critical"],
  SNAPSHOT_ALTERED: ["The stored input no longer matches its recorded hash, so it was not replayed.", "critical"],
};

export default function ReplayPage() {
  const { can } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const [shown, setShown] = useState<Replay | null>(null);
  const runs = useData(["runs", offset], () => api.runs(10, offset));
  const replays = useData(["replays"], api.replays);
  const { run, pending, error } = useAction();
  const start = async (id: string) => { const result = await run(id, () => api.replay(id)); if (result) setShown(result); };
  return (
    <>
      <PageHeading title="Replay" lead="Runs the engine again on a stored input snapshot and its stored settings, and compares everything except the time it took." />
      <div className="space-y-12">
        {error && <ErrorNote error={error} />}
        {shown && <Verdict replay={shown} />}
        <div className="grid gap-12 xl:grid-cols-2">
          <Section title="Planning runs">
            <Loaded data={runs.data} error={runs.error}>{(list) => list.items.length ? (
              <>
                <TableFrame label="Planning runs">
                  <thead><tr><th>Run</th><th>Result</th><th>Planned</th><th><span className="sr-only">Replay</span></th></tr></thead>
                  <tbody>{list.items.map((r) => <tr key={r.run_id}><td><Link href={`/optimization?run=${r.run_id}`} className="mono font-semibold text-tech hover:underline">{r.run_id}</Link><span className="block text-[13px] text-ink-3">{r.change_id}{r.scenario_id !== "base" && `, ${words(r.scenario_id)}`}</span></td><td><Status tone={toneOf(r.approval ?? r.decision)}>{words(r.approval ?? r.decision)}</Status></td><td>{dateTime(r.created_at)}<span className="block text-[13px] text-ink-3">{r.created_by}</span></td><td>{can("REPLAY_RUN") && <Button icon="replay" busy={pending === r.run_id} onClick={() => start(r.run_id)}>Replay</Button>}</td></tr>)}</tbody>
                </TableFrame>
                <Pager total={list.total} limit={10} offset={offset} onChange={setOffset} />
              </>
            ) : <Empty title="No planning run yet" />}</Loaded>
          </Section>
          <Section title="Earlier replays">
            <Loaded data={replays.data} error={replays.error}>{(list) => list.length ? (
              <ul className="divide-y divide-line border-y border-line bg-sheet">{list.map((r) => <li key={r.replay_id}><button type="button" onClick={() => setShown(r)} className="flex w-full flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-left hover:bg-sunken"><span><span className="mono font-semibold">{r.run_id}</span><span className="block text-[13px] text-ink-3">{dateTime(r.created_at)}, {r.created_by}</span></span><Status tone={toneOf(r.status)}>{words(r.status)}</Status></button></li>)}</ul>
            ) : <p className="text-ink-2">None yet.</p>}</Loaded>
          </Section>
        </div>
      </div>
    </>
  );
}

function Verdict({ replay }: { replay: Replay }) {
  const [text, kind] = VERDICT[replay.status];
  const keys = Object.keys(replay.original);
  const show = (v: unknown) => typeof v === "object" && v ? JSON.stringify(v) : String(v ?? "–");
  return (
    <Section title={`Replay of ${replay.run_id}`} note={`${replay.replay_id}, ${dateTime(replay.created_at)} by ${replay.created_by}`}>
      <div className="animate-enter space-y-4">
        <Alert kind={kind} title={words(replay.status)}>{text}</Alert>
        <TableFrame label="Original and reproduced result">
          <thead><tr><th>Field</th><th>Original</th><th>Reproduced</th></tr></thead>
          <tbody>{keys.map((k) => <tr key={k}><td className="font-semibold">{words(k)}</td><td className="mono break-all">{show(replay.original[k])}</td><td className="mono break-all">{replay.reproduced ? show(replay.reproduced[k]) : "–"}</td></tr>)}</tbody>
        </TableFrame>
        {replay.differences.length > 0 && <details open className="text-sm"><summary className="font-semibold">Differences ({replay.differences.length})</summary><ul className="mt-2 space-y-1">{replay.differences.map((d) => <li key={d.field}><strong>{words(d.field)}:</strong> <span className="mono">{d.original}</span> became <span className="mono">{d.reproduced}</span></li>)}</ul></details>}
      </div>
    </Section>
  );
}
