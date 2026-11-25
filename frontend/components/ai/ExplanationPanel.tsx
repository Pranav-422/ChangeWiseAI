"use client";
import { useState } from "react";
import type { Explanation } from "@/lib/api";
import { dateTime, words } from "@/lib/format";
import { Alert, Status, type Tone } from "@/components/ui/primitives";

const LABEL: Record<Explanation["label"], { tone: Tone; text: string }> = {
  AI_GENERATED_VERIFIED: { tone: "active", text: "AI-generated, checked against engine facts" },
  TEMPLATE_GENERATED: { tone: "neutral", text: "Template, filled from engine facts" },
  AWAITING_REVIEW: { tone: "pending", text: "Template shown, AI draft awaits review" },
};

/** Explains and never decides. Every explanation says where its words come from. */
export function ExplanationPanel({ explanation }: { explanation: Explanation }) {
  const [facts, setFacts] = useState(false);
  const label = LABEL[explanation.label];
  const check = explanation.verification as { failures?: unknown[]; sentences?: number } | null;
  return (
    <div className="@container border-l-2 border-tech bg-sheet p-5">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Status tone={label.tone}>{label.text}</Status>
        <span className="text-sm text-ink-3">{explanation.source}, {dateTime(explanation.created_at)}</span>
      </div>
      {explanation.warning && <div className="mb-4"><Alert kind="warning">{explanation.warning}</Alert></div>}
      <div className="gap-x-12 @4xl:columns-2">
        {explanation.sections.map((s) => (
          <div key={s.title} className="mb-4 max-w-[68ch] break-inside-avoid"><h3 className="text-sm font-semibold text-ink-2">{s.title}</h3><p>{s.text}</p></div>
        ))}
      </div>
      {explanation.draft && (
        <details className="mt-5 border border-pending-mark bg-pending-soft p-4">
          <summary className="font-semibold">AI draft, not verified</summary>
          <div className="mt-2 space-y-2">{explanation.draft.map((s) => <p key={s.title}><strong>{s.title}.</strong> {s.text}</p>)}</div>
        </details>
      )}
      <details className="mt-5 text-sm" onToggle={(e) => setFacts(e.currentTarget.open)}>
        <summary className="font-semibold text-tech">Facts and verification</summary>
        {facts && (
          <div className="mt-2 space-y-2">
            <p>Verification: {explanation.verification_status === "NOT_APPLICABLE" ? "not needed, no AI wording is used" : words(explanation.verification_status)}
              {check && `, ${check.sentences ?? 0} sentences checked, ${check.failures?.length ?? 0} refused`}. Engine facts are the only source.</p>
            <pre className="mono max-h-72 overflow-auto border border-line bg-sunken p-3 text-xs whitespace-pre-wrap">{JSON.stringify(explanation.facts, null, 1)}</pre>
            {explanation.verification && <pre className="mono max-h-60 overflow-auto border border-line bg-sunken p-3 text-xs whitespace-pre-wrap">{JSON.stringify(explanation.verification, null, 1)}</pre>}
          </div>
        )}
      </details>
      <p className="mt-4 text-sm text-ink-3">This text explains the engine&apos;s result. It does not approve anything; the planner decides.</p>
    </div>
  );
}
