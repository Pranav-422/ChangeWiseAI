"use client";
import Link from "next/link";
import { RevisionChange } from "@/components/engineering/RevisionMark";
import { STAGES } from "@/components/engineering/StageTrack";
import { useWorkspace } from "@/components/layout/Workspace";
import { PageHeading, Status, TableFrame, toneOf } from "@/components/ui/primitives";
import { dateTime, week, words } from "@/lib/format";

export default function EngineeringChanges() {
  const { changes } = useWorkspace();
  return (
    <>
      <PageHeading title="Engineering changes" lead="Every change in the planning records, with where it stands." />
      <TableFrame label="Engineering changes">
        <thead><tr>{["Change", "Component", "Revision", "Use-up end", "Effective", "Records", "Approval", "Planning", "Stage"].map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
        <tbody>
          {changes.map((c) => (
            <tr key={c.change_id} className="hover:bg-sunken">
              <td><Link href={`/engineering-changes/${c.change_id}`} className="mono font-semibold text-tech hover:underline">{c.change_id}</Link></td>
              <td><span className="mono">{c.part_number}</span><span className="block text-ink-2">{c.reason}</span></td>
              <td><RevisionChange from={c.old_revision} to={c.new_revision} size={20} /></td>
              <td className="mono">{week(c.use_up_end_week)}</td>
              <td className="mono">{week(c.effective_week)}</td>
              <td><Status tone={toneOf(c.validation_status)}>{words(c.validation_status)}</Status></td>
              <td><Status tone={toneOf(c.approval_status)}>{c.approval_status}</Status></td>
              <td>{c.latest_run ? <><Status tone={toneOf(c.latest_run.approval ?? c.latest_run.decision)}>{words(c.latest_run.approval ?? c.latest_run.decision)}</Status><span className="block text-ink-3">{dateTime(c.latest_run.created_at)}</span></> : "Not planned"}</td>
              <td>{STAGES[c.stage] ?? "Closed"}</td>
            </tr>
          ))}
        </tbody>
      </TableFrame>
    </>
  );
}
