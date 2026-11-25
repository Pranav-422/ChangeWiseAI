"use client";
import { useRouter } from "next/navigation";
import { use, useState, type ReactNode } from "react";
import { DocumentText } from "@/components/engineering/DocumentText";
import { useWorkspace } from "@/components/layout/Workspace";
import { Icon } from "@/components/ui/icons";
import { Alert, Button, ErrorNote, Input, Loaded, PageHeading, Section, Select, Status, cx, toneOf, type Tone } from "@/components/ui/primitives";
import { api, type EcnFieldValues, type Review } from "@/lib/api";
import { bytes, dateTime, words } from "@/lib/format";
import { useAction, useData } from "@/lib/hooks";

type Field = keyof EcnFieldValues;
const FIELDS: [Field, string][] = [
  ["change_id", "Change ID"], ["part_number", "Part number"], ["old_revision", "Old revision"], ["new_revision", "New revision"],
  ["effective_week", "Effective week"], ["use_up_end_week", "Use-up end week"], ["interchangeability", "Interchangeable"],
  ["reason", "Reason"], ["approver", "Approver"], ["approval_status", "Approval status"],
];

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, mutate } = useData(["review", id], () => api.review(id));
  return <Loaded data={data} error={error} retry={() => void mutate()}>{(review) => <ReviewWorkspace key={review.review_id} review={review} />}</Loaded>;
}

function ReviewWorkspace({ review }: { review: Review }) {
  const { can } = useWorkspace();
  const router = useRouter();
  const { run, pending, error } = useAction();
  const [edits, setEdits] = useState<Partial<EcnFieldValues>>({});
  const [active, setActive] = useState<Field | null>(null);
  const [compared, setCompared] = useState(false);
  const { extraction: x, validation: v, document: doc } = review;
  const confirmed = review.status === "CONFIRMED";
  const editable = !confirmed && can("SUBMIT_ECN");
  const dirty = Object.keys(edits).length > 0;
  const valid = v.validation_status === "VALID";

  const set = (field: Field, value: EcnFieldValues[Field]) => setEdits((e) => {
    const next = { ...e, [field]: value };
    if (value === review.fields[field]) delete next[field];
    return next;
  });
  const save = async () => { if (await run("save", () => api.updateReview(review.review_id, edits))) setEdits({}); };
  const plan = async () => {
    const result = await run("plan", () => api.optimize(review.review_id));
    if (result) router.push("/optimization");
  };
  const openDocument = async () => {
    const link = await run("open", () => api.documentUrl(doc!.document_id));
    if (link) window.open(link.url, "_blank", "noopener");
  };

  function state(field: Field): { tone: Tone; text: string; detail?: ReactNode } {
    const conflict = v.conflicts.find((c) => c.field === field);
    const ambiguous = v.ambiguous_fields.find((a) => a.field === field);
    const bad = v.validation_errors.find((e) => e.field === field);
    if (bad) return { tone: "critical", text: "Invalid", detail: bad.message };
    if (conflict) return { tone: "critical", text: "Conflict", detail: conflict.values.map((c) => `${String(c.value)} ("${c.source_text}")`).join(" or ") };
    if (ambiguous) return { tone: "pending", text: "Ambiguous", detail: `The document says "${ambiguous.source_text}"` };
    if (v.missing_fields.includes(field)) return { tone: "pending", text: "Missing", detail: "Not in the document. It is never guessed." };
    if (x[field] !== review.fields[field]) return { tone: "active", text: "Corrected by hand", detail: x[field] == null ? "The document gave no value." : `Extracted: ${String(x[field])}` };
    return { tone: "done", text: "Found", detail: x.evidence[field] && <q>{x.evidence[field]}</q> };
  }

  const control = (field: Field, label: string) => {
    const value = field in edits ? edits[field] : review.fields[field];
    const common = { label, hideLabel: true, disabled: !editable, onFocus: () => setActive(field) };
    if (field === "interchangeability") return (
      <Select {...common} value={value == null ? "" : String(value)} onChange={(e) => set(field, e.target.value === "" ? null : e.target.value === "true")}>
        <option value="">Not stated</option><option value="true">Yes</option><option value="false">No</option>
      </Select>);
    if (field === "approval_status") return (
      <Select {...common} value={String(value ?? "")} onChange={(e) => set(field, e.target.value || null)}>
        <option value="">Not stated</option>{["APPROVED", "PENDING", "DRAFT", "REJECTED"].map((s) => <option key={s} value={s}>{words(s)}</option>)}
      </Select>);
    if (field === "effective_week" || field === "use_up_end_week") return (
      <Input {...common} type="number" min={1} max={104} value={value == null ? "" : String(value)} onChange={(e) => set(field, e.target.value === "" ? null : Number(e.target.value))} />);
    return <Input {...common} value={String(value ?? "")} onChange={(e) => set(field, (["reason", "approver"].includes(field) ? e.target.value : e.target.value.toUpperCase()) || null)} />;
  };

  return (
    <>
      <PageHeading title={confirmed ? "Confirmed ECN" : "Review the extraction"}
        lead={<>{doc?.original_filename ?? "Manual entry"}, read by {x.extraction_source}. {Math.round(x.extraction_confidence * 100)}% of the fields have one clear value in the document. That is coverage, not a proof.</>}
        action={doc?.stored && <Button icon="external" busy={pending === "open"} onClick={openDocument}>Open the document</Button>} />
      <div className="mb-8 space-y-3">
        {error && <ErrorNote error={error} />}
        {x.provider_error && <Alert kind="warning">AI extraction failed ({x.provider_error}). The offline rules read the document instead.</Alert>}
        {x.unsupported_values.map((u, i) => <Alert key={i} kind="warning" title={`A proposed ${words(u.field).toLowerCase()} was dropped`}>{String(u.value)}: {u.why}.</Alert>)}
        {v.validation_errors.map((e) => <Alert key={e.code + e.field} kind="critical" title={words(e.code)}>{e.message}</Alert>)}
        {confirmed && <Alert kind="done" title={`Confirmed by ${review.confirmed_by}`}>{dateTime(review.confirmed_at)}. A confirmed ECN cannot be edited; a correction starts a new review.</Alert>}
      </div>
      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <Section title="Document" note={doc ? <>{words(doc.source_kind)}, {bytes(doc.size_bytes)}, {dateTime(doc.uploaded_at)}</> : "No document, entered by hand"}>
          {review.document_text ? (
            <div className="max-h-[70vh] overflow-auto border border-line bg-white p-5" tabIndex={0} role="region" aria-label="Document text">
              <DocumentText text={review.document_text} evidence={x.evidence} active={active} />
            </div>
          ) : <p className="text-ink-2">Type the fields from the paper document.</p>}
          {doc && <p className="mono mt-2 text-xs break-all text-ink-3">SHA-256 {doc.sha256}</p>}
        </Section>
        <Section title="Fields" action={<Status tone={toneOf(v.validation_status)}>{words(v.validation_status)}</Status>}>
          <ul className="divide-y divide-line border-y border-line bg-sheet">
            {FIELDS.map(([field, label]) => {
              const s = state(field);
              return (
                <li key={field} onPointerEnter={() => setActive(field)} className={cx("grid gap-x-4 gap-y-1 px-4 py-3 sm:grid-cols-[130px_minmax(0,1fr)_minmax(0,1fr)]", active === field && "bg-tech-soft/60")}>
                  <span className="self-center font-semibold">{label}</span>
                  {control(field, label)}
                  <span className="self-center text-sm"><Status tone={field in edits ? "active" : s.tone}>{field in edits ? "Not saved" : s.text}</Status>{s.detail && <span className="mt-0.5 block text-[13px] text-ink-2">{s.detail}</span>}</span>
                </li>
              );
            })}
          </ul>
          {editable && (
            <div className="mt-4 flex flex-wrap gap-2">
              <Button kind="dark" disabled={!dirty} busy={pending === "save"} onClick={save}>Save corrections and validate</Button>
              <Button busy={pending === "validate"} disabled={dirty} onClick={() => run("validate", () => api.validateReview(review.review_id))}>Validate again</Button>
              {dirty && <Button kind="quiet" onClick={() => setEdits({})}>Discard</Button>}
            </div>
          )}
          {editable && (
            <div className="mt-8 border-l-4 border-tech bg-sheet p-5">
              <label className="flex items-start gap-3">
                <input type="checkbox" checked={compared} onChange={(e) => setCompared(e.target.checked)} className="mt-1 size-4 accent-tech" />
                <span>I compared these fields with the document.</span>
              </label>
              <Button kind="primary" className="mt-4" icon="check" disabled={!compared || !valid || dirty} busy={pending === "confirm"} onClick={() => run("confirm", () => api.confirmReview(review.review_id))}>Confirm the ECN</Button>
              {(!valid || dirty) && <p className="mt-2 text-sm text-ink-2">{dirty ? "Save the corrections first." : "Confirmation opens when the fields are valid."}</p>}
            </div>
          )}
          {confirmed && can("RUN_PLANNING") && (
            <div className="mt-8 border-l-4 border-tech bg-sheet p-5">
              <p className="display text-2xl">Ready to plan</p>
              <p className="mt-1 mb-4 text-ink-2">Simulates the stock, generates every candidate plan, checks the hard rules and ranks what is left.</p>
              <Button kind="primary" busy={pending === "plan"} onClick={plan}>{pending === "plan" ? "Evaluating plans" : review.latest_run_id ? "Plan again" : "Run the optimization"}{pending !== "plan" && <Icon name="arrow" />}</Button>
            </div>
          )}
        </Section>
      </div>
    </>
  );
}
