import { cx } from "@/components/ui/primitives";

const letter = (revision: string) => revision.replace(/^Rev\s*/i, "");

/** The revision triangle of an engineering drawing: outlined for the outgoing revision, solid for the incoming one. */
export function RevisionMark({ revision, kind, size = 26 }: { revision: string; kind: "old" | "new"; size?: number }) {
  const tone = kind === "old" ? "text-rev-old" : "text-rev-new";
  return (
    <svg viewBox="0 0 28 26" width={size} height={(size * 26) / 28} role="img" aria-label={`Rev ${letter(revision)}`} className={cx("inline-block shrink-0 align-middle", tone)}>
      <path d="M14 2 26.5 24H1.5Z" fill={kind === "new" ? "currentColor" : "var(--color-sheet)"} stroke="currentColor" strokeWidth={2} strokeLinejoin="round" />
      <text x={14} y={20.5} textAnchor="middle" fontSize={12.5} fontWeight={700} fontFamily="var(--font-mono)" fill={kind === "new" ? "#fff" : "currentColor"}>{letter(revision)}</text>
    </svg>
  );
}

export function RevisionChange({ from, to, size }: { from: string; to: string; size?: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <RevisionMark revision={from} kind="old" size={size} />
      <span aria-hidden className="h-px w-4 bg-current" />
      <span className="sr-only">to</span>
      <RevisionMark revision={to} kind="new" size={size} />
    </span>
  );
}

export function Key({ kind, children }: { kind: "old" | "new" | "short" | "stranded"; children: React.ReactNode }) {
  const swatch = { old: "bg-rev-old", new: "bg-rev-new", short: "hatch text-critical border border-critical", stranded: "hatch border border-rev-old text-rev-old" }[kind];
  return <span className="inline-flex items-center gap-1.5 text-[13px] text-ink-2"><span aria-hidden className={cx("size-3", swatch)} />{children}</span>;
}
