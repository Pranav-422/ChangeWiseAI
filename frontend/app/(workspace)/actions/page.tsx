"use client";
import { useState } from "react";
import { useWorkspace } from "@/components/layout/Workspace";
import { Confirm, Drawer } from "@/components/ui/overlay";
import { Button, Empty, ErrorNote, Input, Loaded, PageHeading, Section, Select, Status, TableFrame, toneOf } from "@/components/ui/primitives";
import { api, type ActionItem, type ApprovalList } from "@/lib/api";
import { dateTime, roleName, week, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

export default function ActionsPage() {
  const { me } = useWorkspace();
  const { data, error, mutate } = useData(["actions"], () => api.actions());
  const approvals = useData(["approvals"], api.approvals);
  const [owner, setOwner] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const role = me.role === "PRODUCTION_PLANNER" ? "Planner" : roleName(me.role);
  return (
    <>
      <PageHeading title="Action tracker" lead="Work that comes from an approved plan. Each action belongs to one team and moves one step at a time." />
      <Loaded data={data} error={error} retry={() => void mutate()}>
        {(items) => {
          const shown = items.filter((i) => (!owner || i.owner_role === owner) && (!status || i.status === status));
          const item = items.find((i) => i.action_id === open);
          return (
            <div className="space-y-12">
              <Closing approvals={approvals.data} items={items} />
              {items.length === 0 ? <Empty title="No action yet">Actions are created when a planner approves a plan.</Empty> : (
                <Section title="Actions" action={
                  <div className="flex flex-wrap gap-2">
                    <Select label="Team" hideLabel value={owner} onChange={(e) => setOwner(e.target.value)}><option value="">Every team</option>{[...new Set(items.map((i) => i.owner_role))].map((r) => <option key={r}>{r}</option>)}</Select>
                    <Select label="State" hideLabel value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Every state</option>{["OPEN", "IN_PROGRESS", "DONE"].map((s) => <option key={s} value={s}>{words(s)}</option>)}</Select>
                  </div>}>
                  <TableFrame label="Actions">
                    <thead><tr><th>Action</th><th>Team</th><th>Assignee</th><th>Due</th><th>State</th><th>Updated</th><th><span className="sr-only">Open</span></th></tr></thead>
                    <tbody>{shown.map((i) => (
                      <tr key={i.action_id}>
                        <td><span className="font-semibold">{i.summary}</span><span className="mono block text-[13px] text-ink-3">{i.action_id}, plan {i.plan_id}</span>{i.scenario_id !== "base" && <Status tone="pending">{words(i.scenario_id)}</Status>}</td>
                        <td>{i.owner_role}</td><td>{i.assignee ?? "–"}</td><td className="mono">{week(i.due_week)}</td>
                        <td><Status tone={toneOf(i.status)}>{words(i.status)}</Status></td><td>{dateTime(i.updated_at)}</td>
                        <td><Button onClick={() => setOpen(i.action_id)}>{i.next_status && (role === i.owner_role || role === "Planner") ? "Update" : "Details"}</Button></td>
                      </tr>
                    ))}</tbody>
                  </TableFrame>
                  {!shown.length && <p className="mt-3 text-ink-2">No action matches.</p>}
                </Section>
              )}
              <Drawer open={!!item} onClose={() => setOpen(null)} title={item?.summary ?? ""}>{item && <Detail key={item.action_id} item={item} may={role === item.owner_role || role === "Planner"} />}</Drawer>
            </div>
          );
        }}
      </Loaded>
    </>
  );
}

function Detail({ item, may }: { item: ActionItem; may: boolean }) {
  const { can } = useWorkspace();
  const { run, pending, error } = useAction();
  const [assignee, setAssignee] = useState(item.assignee ?? "");
  const history = useData(["action-history", item.action_id, item.status], () => api.actionHistory(item.action_id));
  const allowed = may && can("UPDATE_ACTION");
  const next = item.next_status as "IN_PROGRESS" | "DONE" | null;
  return (
    <div className="space-y-6">
      {error && <ErrorNote error={error} />}
      <dl className="grid grid-cols-[110px_1fr] gap-y-1.5 text-sm">
        {([["State", words(item.status)], ["Team", item.owner_role], ["Due", week(item.due_week)], ["Action", item.action_id], ["Proposed as", item.plan_action_id ?? "–"], ["Approval", item.approval_id], ["Created", dateTime(item.created_at)]] as const).map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-2">{k}</dt><dd className="mono break-all">{v}</dd></div>)}
      </dl>
      {allowed && next && (
        <div className="space-y-3 border-l-4 border-tech bg-sunken p-4">
          <Input label="Assigned to" value={assignee} maxLength={120} onChange={(e) => setAssignee(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            <Button busy={pending === "assign"} disabled={assignee.trim() === (item.assignee ?? "")} onClick={() => run("assign", () => api.updateAction(item.action_id, { assignee }))}>Save name</Button>
            <Button kind="primary" busy={pending === "advance"} onClick={() => run("advance", () => api.updateAction(item.action_id, { status: next }))}>{next === "IN_PROGRESS" ? "Start" : "Mark done"}</Button>
          </div>
        </div>
      )}
      {!allowed && next && <p className="text-sm text-ink-2">{item.owner_role} or the planner moves this action.</p>}
      <div>
        <h3 className="mb-2 font-semibold">History</h3>
        <ol className="border-l border-line-strong">{history.data?.map((h, i) => <li key={i} className="pb-2 pl-4 text-sm"><span className="font-semibold">{h.from_status ? `${words(h.from_status)} to ${words(h.to_status).toLowerCase()}` : "Created"}</span><span className="block text-ink-2">{h.changed_by ?? "Before the migration"}, {dateTime(h.changed_at)}</span></li>)}</ol>
      </div>
    </div>
  );
}

function Closing({ approvals, items }: { approvals?: ApprovalList; items: ActionItem[] }) {
  const { can } = useWorkspace();
  const { run, pending, error } = useAction();
  const [asking, setAsking] = useState<string | null>(null);
  const open = approvals?.decided.filter((a) => a.decision === "APPROVED" && !a.closed_at) ?? [];
  if (!open.length) return null;
  return (
    <Section title="Approved changes in progress">
      {error && <ErrorNote error={error} />}
      <ul className="space-y-3">{open.map((a) => {
        const mine = items.filter((i) => i.approval_id === a.approval_id), done = mine.filter((i) => i.status === "DONE").length;
        return (
          <li key={a.approval_id} className="flex flex-wrap items-center gap-x-6 gap-y-3 bg-sheet px-5 py-4">
            <div className="min-w-0 flex-1"><p className="font-semibold"><span className="mono">{a.change_id}</span>{a.scenario_id !== "base" && ` (${words(a.scenario_id)})`}: {a.plan_summary}</p>
              <div className="mt-2 flex items-center gap-3"><progress value={done} max={Math.max(1, mine.length)} aria-label={`${done} of ${mine.length} actions done`} className="h-2 w-full max-w-72 accent-done" /><span className="num text-sm">{done} of {mine.length} done</span></div></div>
            {can("CLOSE_CHANGE") && <Button kind="primary" disabled={done < mine.length} onClick={() => setAsking(a.approval_id)}>Close change</Button>}
          </li>
        );
      })}</ul>
      <Confirm open={!!asking} onClose={() => setAsking(null)} busy={!!pending} title="Close this change?" action="Close change"
        onConfirm={async () => { await run("close", () => api.close(asking!)); setAsking(null); }}>Every action is done. Closing is recorded in the audit history and cannot be undone here.</Confirm>
    </Section>
  );
}
