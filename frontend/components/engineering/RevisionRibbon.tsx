import { cx } from "@/components/ui/primitives";
import { RevisionMark } from "./RevisionMark";

type Props = { from: string; to: string; effectiveWeek: number; useUpEnd: number; horizon: number; interchangeable: boolean; compact?: boolean };

/** Revision Transition Ribbon: which revision production may use in each week. */
export function RevisionRibbon({ from, to, effectiveWeek, useUpEnd, horizon, interchangeable, compact }: Props) {
  const weeks = Array.from({ length: horizon }, (_, i) => i + 1);
  const gap = effectiveWeek > useUpEnd + 1;
  const overlap = interchangeable && useUpEnd >= effectiveWeek;
  const span = (a: number, b: number) => ({ gridColumn: `${Math.max(1, a)} / ${Math.min(horizon, b) + 1}` });
  return (
    <figure aria-label={`${from} may be used until week ${useUpEnd}. ${to} starts in week ${effectiveWeek}.`} className="@container min-w-0">
      <div className="grid gap-y-1" style={{ gridTemplateColumns: `repeat(${horizon}, minmax(0, 1fr))` }}>
        <div style={span(1, useUpEnd)} className="relative flex h-9 items-center gap-2 overflow-hidden bg-rev-old-soft pl-2 text-rev-old-ink [clip-path:polygon(0_0,calc(100%-14px)_0,100%_100%,0_100%)]">
          <RevisionMark revision={from} kind="old" size={22} />
          <span className="truncate text-sm font-semibold"><span className="hidden @lg:inline">Phase out, t</span><span className="@lg:hidden">T</span>hrough W{useUpEnd}</span>
        </div>
        {gap && (
          <div style={{ ...span(useUpEnd + 1, effectiveWeek - 1), gridRow: 1 }} className="hatch flex h-9 items-center justify-center border border-critical text-critical">
            <span className="bg-sheet px-1 text-xs font-semibold">Gap</span>
          </div>
        )}
        <div style={{ ...span(effectiveWeek, horizon), gridRow: 2 }} className="flex h-9 items-center gap-2 overflow-hidden bg-rev-new-soft pl-2 text-tech-strong [clip-path:polygon(14px_0,100%_0,100%_100%,0_100%)]">
          <span className="ml-3"><RevisionMark revision={to} kind="new" size={22} /></span>
          <span className="truncate text-sm font-semibold"><span className="hidden @lg:inline">Phase in, f</span><span className="@lg:hidden">F</span>rom W{effectiveWeek}</span>
        </div>
        {weeks.map((n) => (
          <div key={n} style={{ gridRow: 3, gridColumn: n }} className={cx("mono border-t pt-0.5 text-center text-xs", n === effectiveWeek ? "border-t-2 border-rev-new font-semibold text-tech-strong" : n === useUpEnd ? "border-t-2 border-rev-old text-rev-old" : "border-line-strong text-ink-3")}>
            W{n}
          </div>
        ))}
      </div>
      {!compact && (
        <figcaption className="mt-2 text-sm text-ink-2">
          {gap ? `No revision is permitted from W${useUpEnd + 1} to W${effectiveWeek - 1}.`
            : overlap ? `Both revisions may be used from W${effectiveWeek} to W${useUpEnd}, ${to} first.`
            : `The revisions hand over between W${useUpEnd} and W${effectiveWeek}.`}
          {interchangeable ? " They are interchangeable." : " They are not interchangeable."}
        </figcaption>
      )}
    </figure>
  );
}
