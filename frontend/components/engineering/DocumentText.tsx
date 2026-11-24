import { Fragment, type ReactNode } from "react";

/** The document with every quoted passage marked. `active` is the field being looked at. */
export function DocumentText({ text, evidence, active }: { text: string; evidence: Record<string, string>; active: string | null }) {
  // quotes were matched ignoring white space, so find them the same way
  const marks: { start: number; end: number; field: string }[] = [];
  Object.entries(evidence).forEach(([field, quote]) => {
    const pattern = quote.trim().split(/\s+/).map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
    const match = pattern && new RegExp(pattern, "i").exec(text);
    if (match) marks.push({ start: match.index, end: match.index + match[0].length, field });
  });
  const focused = marks.find((m) => m.field === active);
  const others = marks.filter((m) => m !== focused && !(focused && m.start < focused.end && m.end > focused.start));
  const ordered = [...others, ...(focused ? [focused] : [])].sort((a, b) => a.start - b.start);
  const parts: ReactNode[] = [];
  let at = 0;
  ordered.forEach((m) => {
    if (m.start < at) return;
    parts.push(<Fragment key={`t${at}`}>{text.slice(at, m.start)}</Fragment>);
    parts.push(<mark key={m.field} className={m.field === active ? "bg-tech text-white" : "bg-tech-soft text-ink"}>{text.slice(m.start, m.end)}</mark>);
    at = m.end;
  });
  parts.push(<Fragment key="rest">{text.slice(at)}</Fragment>);
  return <pre className="mono text-[13px] leading-relaxed whitespace-pre-wrap">{parts}</pre>;
}
