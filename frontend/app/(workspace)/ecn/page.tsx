"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type DragEvent } from "react";
import { useWorkspace } from "@/components/layout/Workspace";
import { Icon } from "@/components/ui/icons";
import { Pager, Tabs } from "@/components/ui/overlay";
import { Alert, Button, Empty, ErrorNote, Loaded, PageHeading, Section, Select, Status, TableFrame, Textarea, cx, toneOf } from "@/components/ui/primitives";
import { api, type Document } from "@/lib/api";
import { bytes, dateTime, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

const LIMIT = 15;

export default function EcnIntake() {
  const { can } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const { data, error, mutate } = useData(["reviews", offset], () => api.reviews(LIMIT, offset));
  return (
    <>
      <PageHeading title="ECN intake" lead="Read an engineering change notice, compare what was extracted with the document, and confirm it. Only a confirmed ECN can be planned." />
      <div className="grid gap-12 xl:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
        {can("SUBMIT_ECN") ? <Intake /> : <Section title="New document"><Alert>Your role reads reviews. Engineering and planning submit documents.</Alert></Section>}
        <Section title="Document reviews">
          <Loaded data={data} error={error} retry={() => void mutate()}>
            {(list) => (
              <>
                {list.unread_documents.length > 0 && (
                  <ul className="mb-5 space-y-2">{list.unread_documents.map((d) => <Unread key={d.document_id} doc={d} />)}</ul>
                )}
                {list.items.length === 0 ? <Empty title="No review yet">Upload a document or load a sample to start.</Empty> : (
                  <TableFrame label="Document reviews">
                    <thead><tr><th>Review</th><th>Document</th><th>Change</th><th>Fields</th><th>Confirmation</th><th>Received</th></tr></thead>
                    <tbody>{list.items.map((r) => (
                      <tr key={r.review_id} className="hover:bg-sunken">
                        <td><Link href={`/ecn/${r.review_id}`} className="mono font-semibold text-tech hover:underline">{r.review_id}</Link></td>
                        <td>{r.original_filename ?? "Manual entry"}<span className="block text-[13px] text-ink-3">{r.extraction_source}</span></td>
                        <td className="mono">{r.fields.change_id ?? "not found"}{r.scenario_id !== "base" && <span className="block text-[13px] text-pending">{words(r.scenario_id)}</span>}</td>
                        <td><Status tone={toneOf(r.validation_status)}>{words(r.validation_status)}</Status></td>
                        <td>{r.status === "CONFIRMED" ? <Status tone="done">Confirmed</Status> : <Status tone="pending">Waiting</Status>}{r.confirmed_by && <span className="block text-[13px] text-ink-3">{r.confirmed_by}</span>}</td>
                        <td>{dateTime(r.created_at)}<span className="block text-[13px] text-ink-3">{r.created_by}</span></td>
                      </tr>
                    ))}</tbody>
                  </TableFrame>
                )}
                <Pager total={list.total} limit={LIMIT} offset={offset} onChange={setOffset} />
              </>
            )}
          </Loaded>
        </Section>
      </div>
    </>
  );
}

function Unread({ doc }: { doc: Document }) {
  const { can, change, scenario } = useWorkspace();
  const router = useRouter();
  const { run, pending, error } = useAction();
  const open = async (work: () => Promise<{ review_id: string }>) => {
    const review = await run("read", work);
    if (review) router.push(`/ecn/${review.review_id}`);
  };
  return (
    <li>
      <Alert kind={doc.extraction_status === "FAILED" ? "critical" : "warning"} title={doc.original_filename}
        action={can("SUBMIT_ECN") && (doc.extraction_status === "FAILED"
          ? <Button busy={!!pending} onClick={() => open(() => api.manualReview(change.change_id, scenario))}>Enter fields by hand</Button>
          : <Button busy={!!pending} onClick={() => open(() => api.extract(doc.document_id))}>Extract fields</Button>)}>
        {doc.extraction_error ?? "Stored, not read yet."} {bytes(doc.size_bytes)}, {dateTime(doc.uploaded_at)}
        {error && ` ${error.message}`}
      </Alert>
    </li>
  );
}

function Intake() {
  const { change, scenario } = useWorkspace();
  const router = useRouter();
  const { run, pending, error } = useAction();
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [sample, setSample] = useState("");
  const [over, setOver] = useState(false);
  const samples = useData(["samples"], api.samples);

  const read = async (store: () => Promise<Document>) => {
    const review = await run("read", async () => api.extract((await store()).document_id));
    if (review) router.push(`/ecn/${review.review_id}`);
  };
  const manual = async () => {
    const review = await run("manual", () => api.manualReview(change.change_id, scenario));
    if (review) router.push(`/ecn/${review.review_id}`);
  };
  const drop = (e: DragEvent) => { e.preventDefault(); setOver(false); setFile(e.dataTransfer.files[0] ?? null); };
  const busy = pending === "read";

  return (
    <Section title="New document" note={`For ${change.change_id}. Files are stored privately and only engineering roles can open them.`}>
      {error && <div className="mb-4"><ErrorNote error={error} /></div>}
      <Tabs label="Source" tabs={[
        { id: "file", title: "Upload", content: (
          <div className="space-y-4">
            <label onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}
              className={cx("drafting flex min-h-52 cursor-pointer flex-col items-center justify-center gap-2 border-2 border-dashed bg-sheet p-6 text-center transition-colors focus-within:border-tech hover:border-tech", over ? "border-tech bg-tech-soft" : "border-line-strong")}>
              <Icon name={file ? "file" : "upload"} size={30} className="text-tech" />
              <span className="font-semibold">{file ? file.name : "Drop the ECN here, or choose a file"}</span>
              <span className="text-sm text-ink-2">{file ? bytes(file.size) : "PDF with a text layer, or plain text. Up to 4 MB."}</span>
              <input type="file" accept=".pdf,.txt,application/pdf,text/plain" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <Button kind="primary" className="w-full" disabled={!file} busy={busy} onClick={() => file && read(() => api.upload(change.change_id, scenario, file))}>Store and extract fields</Button>
          </div>) },
        { id: "text", title: "Paste text", content: (
          <div className="space-y-4">
            <Textarea label="Document text" rows={9} value={text} onChange={(e) => setText(e.target.value)} />
            <Button kind="primary" className="w-full" disabled={text.trim().length < 30} busy={busy} onClick={() => read(() => api.upload(change.change_id, scenario, text))}>Store and extract fields</Button>
          </div>) },
        { id: "sample", title: "Sample", content: (
          <div className="space-y-4">
            <Select label="Member 1 test document" value={sample} onChange={(e) => setSample(e.target.value)} hint="Eighteen synthetic ECNs. Some are incomplete or contradictory on purpose.">
              <option value="">Choose</option>
              {samples.data?.map((s) => <option key={s}>{s}</option>)}
            </Select>
            <Button kind="primary" className="w-full" disabled={!sample} busy={busy} onClick={() => read(() => api.uploadSample(change.change_id, scenario, sample))}>Store and extract fields</Button>
          </div>) },
      ]} />
      <p className="mt-5 border-t border-line pt-4 text-sm text-ink-2">
        No readable document? <button type="button" onClick={manual} disabled={!!pending} className="font-semibold text-tech hover:underline">Enter the fields by hand</button>
      </p>
    </Section>
  );
}
