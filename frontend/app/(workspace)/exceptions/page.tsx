"use client";
import { useState } from "react";
import { SeverityRail } from "@/components/exceptions/SeverityRail";
import { useWorkspace } from "@/components/layout/Workspace";
import { Button, Empty, ErrorNote, Loaded, PageHeading, Select, Status, toneOf } from "@/components/ui/primitives";
import { api, type ExceptionItem } from "@/lib/api";
import { roleName, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

const LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;
const FILTERS = [["severity_level", "Severity"], ["status", "State"], ["owner_role", "Owner"], ["exception_type", "Type"]] as const;
type Key = (typeof FILTERS)[number][0];

export default function ExceptionsPage() {
  const { me, can, change, scenario } = useWorkspace();
  const { data, error, mutate } = useData(["exceptions", change.change_id, scenario], () => api.exceptions(change.change_id, scenario));
  const { run, pending, error: failed } = useAction();
  const [filters, setFilters] = useState<Partial<Record<Key, string>>>({});
  const role = me.role === "PRODUCTION_PLANNER" ? "Planner" : roleName(me.role);
  const update = (item: ExceptionItem, status: string) => run(item.exception_id, () => api.updateException(item.exception_id, {
    change_id: change.change_id, scenario, status: status as "ACKNOWLEDGED" | "RESOLVED" }));
  return (
    <>
      <PageHeading title="Exceptions" lead="Scored and ranked by Member 1's severity engine, worst first. The order does not depend on the filters." />
      <Loaded data={data} error={error} retry={() => void mutate()}>
        {({ items }) => {
          const shown = items.filter((e) => FILTERS.every(([k]) => !filters[k] || e[k] === filters[k]));
          return (
            <div className="grid gap-8 xl:grid-cols-[230px_minmax(0,1fr)]">
              <aside className="space-y-6">
                <ul aria-label="Count by severity" className="space-y-1">
                  {LEVELS.map((l) => { const n = items.filter((e) => e.severity_level === l).length; return (
                    <li key={l} className="flex items-center justify-between gap-3 border-b border-line py-1.5"><Status tone={toneOf(l)}>{words(l)}</Status><span className="display text-2xl">{n}</span></li>); })}
                </ul>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  {FILTERS.map(([k, label]) => (
                    <Select key={k} label={label} value={filters[k] ?? ""} onChange={(e) => setFilters((f) => ({ ...f, [k]: e.target.value }))}>
                      <option value="">All</option>{[...new Set(items.map((e) => String(e[k])))].map((v) => <option key={v} value={v}>{k === "owner_role" ? v : words(v)}</option>)}
                    </Select>
                  ))}
                </div>
              </aside>
              <div className="min-w-0 space-y-4">
                {failed && <ErrorNote error={failed} />}
                {shown.length === 0 ? <Empty title={items.length ? "No exception matches the filters" : "No exception"}>{items.length ? "Clear a filter to see the others." : "The simulation found nothing to act on."}</Empty> : (
                  <SeverityRail items={shown}>
                    {(e) => can("UPDATE_EXCEPTION") && e.owner_roles.includes(role) && e.allowed_statuses.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">{e.allowed_statuses.map((s) => <Button key={s} busy={pending === e.exception_id} onClick={() => update(e, s)}>{s === "ACKNOWLEDGED" ? "Acknowledge" : "Mark resolved"}</Button>)}</div>
                    )}
                  </SeverityRail>
                )}
              </div>
            </div>
          );
        }}
      </Loaded>
    </>
  );
}
