"use client";
import { useState } from "react";
import { useWorkspace } from "@/components/layout/Workspace";
import { Tabs } from "@/components/ui/overlay";
import { Alert, Button, ErrorNote, Facts, Input, LinkButton, Loaded, PageHeading, Section, Select, Status, TableFrame } from "@/components/ui/primitives";
import { api, type Role, type UserRow } from "@/lib/api";
import { env } from "@/lib/env";
import { dateTime, roleName, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

const ROLES: Role[] = ["ADMIN", "ENGINEERING", "PURCHASING", "PRODUCTION_PLANNER", "QUALITY", "VIEWER"];

export default function SettingsPage() {
  const { can } = useWorkspace();
  return (
    <>
      <PageHeading title="Profile and settings" />
      <Tabs label="Settings" tabs={[
        { id: "profile", title: "Profile", content: <Profile /> },
        ...(can("MANAGE_USERS") ? [{ id: "access", title: "Access", content: <Access /> }] : []),
        { id: "system", title: "System", content: <System /> },
      ]} />
    </>
  );
}

function Profile() {
  const { me, signOut } = useWorkspace();
  const { run, pending, error } = useAction();
  const [name, setName] = useState(me.name);
  return (
    <div className="grid gap-12 xl:grid-cols-2">
      <Section title="You">
        {error && <ErrorNote error={error} />}
        <div className="max-w-md space-y-4">
          <Input label="Name shown in decisions and audit events" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} hint="Earlier records keep the name they were written with." />
          <div className="flex flex-wrap gap-2"><Button kind="primary" disabled={!name.trim() || name === me.name} busy={!!pending} onClick={() => run("rename", () => api.rename(name))}>Save</Button><LinkButton href="/update-password">Change password</LinkButton><Button icon="exit" onClick={signOut}>Sign out</Button></div>
        </div>
      </Section>
      <Section title="Access">
        <Facts columns={1} items={[["Email", me.email], ["Role", roleName(me.role)], ["You may", me.permissions.map((p) => words(p).toLowerCase()).join(", ")]]} />
      </Section>
    </div>
  );
}

function Access() {
  const { data, error } = useData(["users"], api.users);
  return (
    <Section title="People" note="A role decides what a person may do, in the interface and in every backend call. Each change is audited.">
      <Loaded data={data} error={error}>{(users) => (
        <TableFrame label="People">
          <thead><tr><th>Person</th><th>Role</th><th>Access</th><th>Since</th></tr></thead>
          <tbody>{users.map((u) => <Person key={u.user_id} user={u} />)}</tbody>
        </TableFrame>
      )}</Loaded>
    </Section>
  );
}

function Person({ user }: { user: UserRow }) {
  const { me } = useWorkspace();
  const { run, pending, error } = useAction();
  const own = user.user_id === me.user_id;
  return (
    <tr>
      <td><span className="font-semibold">{user.full_name || user.email}</span><span className="block text-[13px] text-ink-3">{user.email}</span>{error && <span className="block text-critical">{error.message}</span>}</td>
      <td className="min-w-52"><Select label={`Role of ${user.email}`} hideLabel value={user.role} disabled={own || !!pending} onChange={(e) => run("role", () => api.updateUser(user.user_id, { role: e.target.value as Role }))}>{ROLES.map((r) => <option key={r} value={r}>{roleName(r)}</option>)}</Select></td>
      <td><span className="flex flex-wrap items-center gap-2"><Status tone={user.is_active ? "done" : "neutral"}>{user.is_active ? "Active" : "No access"}</Status>{!own && <Button busy={pending === "active"} onClick={() => run("active", () => api.updateUser(user.user_id, { is_active: !user.is_active }))}>{user.is_active ? "Remove access" : "Give access"}</Button>}</span></td>
      <td>{dateTime(user.created_at)}</td>
    </tr>
  );
}

type Ready = { status: string; database: boolean; ai: string; storage: boolean; auth: boolean };

function System() {
  const { data, error } = useData(["ready"], async () => (await fetch(`${env.apiBaseUrl}/ready`, { cache: "no-store" })).json() as Promise<Ready>);
  return (
    <Section title="Services">
      <Loaded data={data} error={error}>{(r) => (
        <div className="max-w-2xl space-y-4">
          <Facts items={[["Planning service", <Status key="a" tone={r.status === "ready" ? "done" : "critical"}>{words(r.status)}</Status>], ["Database", <Status key="b" tone={r.database ? "done" : "critical"}>{r.database ? "Connected" : "Not reachable"}</Status>],
            ["Document storage", <Status key="c" tone={r.storage ? "done" : "pending"}>{r.storage ? "Configured" : "Not configured"}</Status>], ["AI", r.ai === "fallback" ? "No key set" : r.ai]]} />
          {r.ai === "fallback" && <Alert>Extraction uses offline rules and explanations use templates filled from engine facts.</Alert>}
        </div>
      )}</Loaded>
    </Section>
  );
}
