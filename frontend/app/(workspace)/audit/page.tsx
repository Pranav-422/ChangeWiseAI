"use client";
import { useState, type FormEvent } from "react";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { Drawer, Pager } from "@/components/ui/overlay";
import { Alert, Button, Empty, Input, LinkButton, Loaded, PageHeading, Select } from "@/components/ui/primitives";
import { api, type AuditEvent } from "@/lib/api";
import { dateTime, qty, words } from "@/lib/format";
import { useData } from "@/lib/hooks";

const LIMIT = 40;

export default function AuditPage() {
  const [offset, setOffset] = useState(0);
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");
  const [event, setEvent] = useState<AuditEvent | null>(null);
  const chain = useData(["chain"], api.chain);
  const { data, error, mutate } = useData(["audit", offset, type, search], () => api.audit({ limit: LIMIT, offset, event_type: type, search }));
  const find = (e: FormEvent<HTMLFormElement>) => { e.preventDefault(); setOffset(0); setSearch(String(new FormData(e.currentTarget).get("q") ?? "").trim()); };
  return (
    <>
      <PageHeading title="Audit history" lead="Every state change, in order, written in the same transaction as the change itself." action={<LinkButton href="/replay" icon="arrow">Replay a run</LinkButton>} />
      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_330px]">
        <div className="min-w-0">
          <form onSubmit={find} className="mb-6 flex flex-wrap items-end gap-2">
            <div className="min-w-56 flex-1"><Input label="Search events, people and references" name="q" defaultValue={search} maxLength={100} /></div>
            <div className="min-w-48"><Select label="Event" value={type} onChange={(e) => { setType(e.target.value); setOffset(0); }}><option value="">Every event</option>{data?.event_types.map((t) => <option key={t} value={t}>{words(t)}</option>)}</Select></div>
            <Button type="submit" icon="search">Search</Button>
          </form>
          <Loaded data={data} error={error} retry={() => void mutate()}>
            {(page) => page.items.length ? <><AuditTimeline events={page.items} onSelect={setEvent} /><Pager total={page.total} limit={LIMIT} offset={offset} onChange={setOffset} /></> : <Empty title="No event matches" />}
          </Loaded>
        </div>
        <aside className="space-y-4">
          <Loaded data={chain.data} error={chain.error}>
            {(c) => (
              <>
                {c.intact ? <Alert kind="done" title="Hash chain intact">{qty(c.events)} events. None was altered, removed or reordered inside the log.</Alert> : <Alert kind="critical" title={`Chain broken at event ${c.broken_at}`}>The log was changed outside the application.</Alert>}
                {c.head_hash && <p className="mono text-xs break-all text-ink-3">Latest hash {c.head_hash}</p>}
              </>
            )}
          </Loaded>
          <p className="text-sm text-ink-2">The chain shows changes inside the log. It cannot show that the newest events were cut off, or a full rewrite by someone who administers the database. Keep a copy of the latest hash elsewhere to detect that.</p>
        </aside>
      </div>
      <Drawer open={!!event} onClose={() => setEvent(null)} title={words(event?.event_type)}>
        {event && (
          <div className="space-y-4 text-sm">
            <dl className="grid grid-cols-[100px_1fr] gap-y-1.5">
              {([["Event", String(event.seq)], ["When", dateTime(event.created_at)], ["Who", `${event.user_name} (${event.role})`], ["Reference", event.entity_id], ["Source", event.source], ["Hash", event.event_hash], ["Follows", event.previous_hash]] as const).map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-2">{k}</dt><dd className="mono break-all">{v}</dd></div>)}
            </dl>
            <pre className="mono overflow-auto border border-line bg-sunken p-3 text-xs whitespace-pre-wrap">{JSON.stringify(event.payload, null, 1)}</pre>
          </div>
        )}
      </Drawer>
    </>
  );
}
