"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { roleName, week, words } from "@/lib/format";
import { RevisionChange } from "@/components/engineering/RevisionMark";
import { STAGES } from "@/components/engineering/StageTrack";
import { Icon } from "@/components/ui/icons";
import { IconButton, Status, cx, toneOf } from "@/components/ui/primitives";
import { Menu } from "@/components/ui/overlay";
import { QuickJump } from "./QuickJump";
import { locate } from "./navigation";
import { useWorkspace } from "./Workspace";

function Cell({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={cx("flex min-w-0 flex-col justify-center border-l border-line px-4 py-2 first:border-l-0", className)}>
      <dt className="tag">{label}</dt>
      <dd className="flex min-h-6 items-center truncate text-[15px] font-semibold">{children}</dd>
    </div>
  );
}

/** The drawing's title block: which change is open, always in the same place. */
export function TitleBlock({ onMenu }: { onMenu: () => void }) {
  const { me, change, changes, scenario, select, signOut } = useWorkspace();
  const place = locate(usePathname());
  return (
    <header className="no-print sticky top-0 z-30 border-b-2 border-ink bg-sheet">
      <div className="flex min-h-12 items-center gap-2 border-b border-line px-2 sm:px-8">
        <IconButton icon="menu" label="Open navigation" onClick={onMenu} className="lg:hidden" />
        <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
          <ol className="flex items-center gap-2 truncate text-sm">
            {place && <>
              <li className="mono hidden text-ink-3 sm:block">{place.ref}</li>
              <li className="hidden text-ink-2 sm:block">{place.group.title}</li>
              <li aria-hidden className="hidden text-ink-3 sm:block"><Icon name="right" size={13} /></li>
              <li className="truncate font-semibold" aria-current="page"><Link href={place.item.href}>{place.item.title}</Link></li>
            </>}
          </ol>
        </nav>
        <QuickJump />
        <Menu label={<span className="flex min-h-10 items-center gap-2 rounded-sharp px-2 text-sm hover:bg-neutral-soft"><Icon name="user" size={18} /><span className="hidden max-w-40 truncate font-semibold md:block">{me.name}</span><Icon name="down" size={14} /></span>}>
          <div className="border-b border-line px-3 py-2 text-sm"><p className="font-semibold">{me.name}</p>{me.email && <p className="text-ink-2">{me.email}</p>}<p className="text-ink-2">{roleName(me.role)}</p></div>
          <Link href="/settings" className="flex min-h-10 items-center gap-2 px-3 text-sm hover:bg-sunken">Profile and settings</Link>
          <button type="button" onClick={signOut} className="flex min-h-10 w-full items-center gap-2 px-3 text-sm hover:bg-sunken"><Icon name="exit" />Sign out</button>
        </Menu>
      </div>
      <dl className="grid grid-cols-[1fr_1fr] sm:flex sm:px-4">
        <Cell label="Change" className="sm:min-w-32">
          {changes.length > 1 ? (
            <select aria-label="Engineering change" value={change.change_id} onChange={(e) => select(e.target.value, "base")} className="mono w-full bg-transparent font-semibold">
              {changes.map((c) => <option key={c.change_id}>{c.change_id}</option>)}
            </select>
          ) : <Link href={`/engineering-changes/${change.change_id}`} className="mono hover:underline">{change.change_id}</Link>}
        </Cell>
        <Cell label="Revision"><RevisionChange from={change.old_revision} to={change.new_revision} size={20} /></Cell>
        <Cell label="Part" className="hidden md:flex"><span className="mono">{change.part_number} <span aria-hidden>→</span><span className="sr-only">to</span> {change.new_material_id}</span></Cell>
        <Cell label="Use-up / effective" className="hidden sm:flex"><span className="mono">{week(change.use_up_end_week)} / {week(change.effective_week)}</span></Cell>
        {/* both describe the current records, so a test variant does not show them */}
        {scenario === "base" && <Cell label="Records" className="hidden xl:flex"><Status tone={toneOf(change.validation_status)}>{words(change.validation_status)}</Status></Cell>}
        {scenario === "base" && <Cell label="Next stage" className="hidden lg:flex"><span className="truncate">{STAGES[change.stage] ?? "Closed"}</span></Cell>}
        <Cell label="Data variant" className={cx("col-span-2 border-t border-line sm:ml-auto sm:max-w-72 sm:border-t-0", scenario !== "base" && "bg-pending-soft")}>
          <select aria-label="Data variant" value={scenario} onChange={(e) => select(change.change_id, e.target.value)} className="w-full truncate bg-transparent font-semibold">
            {change.scenarios.map((s) => <option key={s.scenario_id} value={s.scenario_id}>{s.scenario_id === "base" ? "Current records" : words(s.scenario_id)}</option>)}
          </select>
        </Cell>
      </dl>
      {scenario !== "base" && (
        <p className="border-t border-pending-mark bg-pending-soft px-4 py-1.5 text-sm sm:px-8"><strong>Test variant.</strong> {change.scenarios.find((s) => s.scenario_id === scenario)?.description} These are not the current records.</p>
      )}
    </header>
  );
}
