"use client";
import { useState } from "react";
import type { Inventory, Week } from "@/lib/api";
import { qty, weekRange } from "@/lib/format";
import { Key } from "@/components/engineering/RevisionMark";
import { useWidth } from "./useWidth";

type Order = Pick<Inventory["purchase_orders"][number], "po_id" | "material_id" | "quantity" | "arrival_week">;
type Props = {
  weeks: Week[]; effectiveWeek: number; useUpEnd: number; oldRevision: string; newRevision: string;
  orders?: Order[]; oldMaterial?: string; title?: string;
};

const LANE = { receipts: 46, stock: 92, demand: 66, gap: 22 };

/** Round axis top: 1, 2, 2.5 or 5 times a power of ten. */
export function niceMax(value: number) {
  if (value <= 0) return 10;
  const power = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 2.5, 5, 10].map((m) => m * power).find((m) => m >= value)!;
}

/** Closing stock as a step line: flat through the week, changing at its end. */
function steps(values: number[], x: (i: number) => number, y: (v: number) => number) {
  return values.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)} L${x(i + 1)},${y(v)}`).join(" ");
}

/**
 * Material Flow Timeline. One sheet, one week axis, four lanes: receipts, outgoing stock, incoming stock, demand.
 * Both stock lanes share a scale, so their areas can be compared. Values are drawn as received from the engine.
 */
export function MaterialFlow({ weeks, effectiveWeek, useUpEnd, oldRevision, newRevision, orders = [], oldMaterial, title }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  if (!weeks.length) return null;

  const left = width < 520 ? 36 : 116, right = 8, top = 30;
  const step = (width - left - right) / weeks.length;
  const x = (i: number) => left + i * step;
  const first = weeks[0]!.week;
  const stockTop = niceMax(Math.max(...weeks.flatMap((w) => [w.rev_b_closing, w.rev_c_closing])));
  const demandTop = niceMax(Math.max(...weeks.map((w) => w.demand)));
  const yReceipts = top, yOld = yReceipts + LANE.receipts + LANE.gap, yNew = yOld + LANE.stock + LANE.gap;
  const yDemand = yNew + LANE.stock + LANE.gap, bottom = yDemand + LANE.demand, height = bottom + 24;
  const stockY = (base: number) => (v: number) => base + LANE.stock - (v / stockTop) * LANE.stock;
  const demandY = (v: number) => (v / demandTop) * LANE.demand;
  const short = weeks.filter((w) => w.shortage > 0);
  const boundary = (w: number) => x(Math.min(weeks.length, Math.max(0, w - first)));
  const narrow = step < 62;
  const shown = active === null ? null : weeks[active]!;

  const lane = (base: number, values: number[], tone: "old" | "new", label: string) => {
    const y = stockY(base), path = steps(values, x, y), color = `var(--color-rev-${tone})`;
    const floor = base + LANE.stock;
    const strandedFrom = weeks.findIndex((w) => w.week > useUpEnd);
    const room = strandedFrom >= 0 && floor - y(Math.max(0, ...values.slice(strandedFrom))) > 36;
    const stranded = tone === "old" && strandedFrom >= 0 && values.slice(strandedFrom).some((v) => v > 0);
    return (
      <g>
        <path d={`${path} L${x(values.length)},${floor} L${x(0)},${floor} Z`} fill={`var(--color-rev-${tone}-soft)`} className="transition-all duration-300" />
        {stranded && (
          <g>
            <path d={`M${x(strandedFrom)},${floor} ${steps(values.slice(strandedFrom), (i) => x(i + strandedFrom), y).replace("M", "L")} L${x(values.length)},${floor} Z`} fill="url(#stranded)" />
            {room && !narrow && <>
              <rect x={x(strandedFrom) + 8} y={floor - 25} width={120} height={17} fill="var(--color-sheet)" />
              <text x={x(strandedFrom) + 13} y={floor - 12.5} fontSize={12} fontWeight={600} fill="var(--color-rev-old)">Not usable after W{useUpEnd}</text>
            </>}
          </g>
        )}
        <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" className="transition-all duration-300" />
        <line x1={left} x2={width - right} y1={floor} y2={floor} stroke="var(--color-line-strong)" />
        <text x={left - 8} y={base + 9} textAnchor="end" fontFamily="var(--font-mono)" fontSize={11} fill="var(--color-ink-3)">{qty(stockTop)}</text>
        <text x={left - 8} y={floor} textAnchor="end" fontFamily="var(--font-mono)" fontSize={11} fill="var(--color-ink-3)">0</text>
        {width >= 520 && <text x={12} y={base + LANE.stock / 2 + 4} fontSize={13} fontWeight={600} fill="var(--color-ink)">{label}</text>}
        {values.map((v, i) => (!narrow || i % 2 === values.length % 2) && (
          <text key={i} x={x(i) + step / 2} y={Math.min(floor - 5, y(v) - 5 < base + 8 ? y(v) + 14 : y(v) - 5)} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={11.5} fill="var(--color-ink)">{qty(v)}</text>
        ))}
      </g>
    );
  };

  const summary = short.length
    ? `Demand is not met in ${weekRange(short.map((w) => w.week))}.` : "Demand is met in every week.";
  return (
    <figure className="min-w-0">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-x-5 gap-y-1">
        {title && <figcaption className="font-semibold">{title}</figcaption>}
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <Key kind="old">{oldRevision} stock</Key><Key kind="new">{newRevision} stock</Key>
          {weeks.some((w) => w.week > useUpEnd && w.rev_b_closing > 0) && <Key kind="stranded">{oldRevision} not usable</Key>}
          {short.length > 0 && <Key kind="short">Unmet</Key>}
        </div>
      </div>
      <div ref={ref} className="drafting relative border border-line bg-sheet" onPointerLeave={() => setActive(null)}>
        <svg width={width} height={height} role="img" aria-label={`Material flow by week. ${summary}`} className="block max-w-full">
          {active !== null && <rect x={x(active)} y={0} width={step} height={bottom} fill="var(--color-tech)" opacity={0.07} />}
          {/* receipts */}
          <line x1={left} x2={width - right} y1={yReceipts + LANE.receipts} y2={yReceipts + LANE.receipts} stroke="var(--color-line-strong)" />
          {width >= 520 && <text x={12} y={yReceipts + LANE.receipts / 2 + 8} fontSize={13} fontWeight={600} fill="var(--color-ink)">Receipts</text>}
          {weeks.map((w, i) => {
            const mark = (value: number, tone: "old" | "new", dx: number) => value > 0 && (
              <g key={tone} transform={`translate(${x(i) + step / 2 + dx}, ${yReceipts + LANE.receipts})`}>
                <path d="M0,-2 L-6,-13 L6,-13 Z" fill={`var(--color-rev-${tone})`} />
                <text y={-18} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={11.5} fill="var(--color-ink)">+{qty(value)}</text>
                {!narrow && orders.filter((o) => o.arrival_week === w.week && (o.material_id === oldMaterial) === (tone === "old") && o.quantity === value).slice(0, 1).map((o) => (
                  <text key={o.po_id} y={-32} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={10.5} fill="var(--color-ink-3)">{o.po_id}</text>
                ))}
              </g>
            );
            const both = w.rev_b_receipts > 0 && w.rev_c_receipts > 0;
            return <g key={w.week}>{mark(w.rev_b_receipts, "old", both ? -16 : 0)}{mark(w.rev_c_receipts, "new", both ? 16 : 0)}</g>;
          })}
          {lane(yOld, weeks.map((w) => w.rev_b_closing), "old", `${oldRevision} stock`)}
          {lane(yNew, weeks.map((w) => w.rev_c_closing), "new", `${newRevision} stock`)}
          {/* demand: used old, used new, unmet */}
          {width >= 520 && <text x={12} y={yDemand + LANE.demand / 2 + 4} fontSize={13} fontWeight={600} fill="var(--color-ink)">Demand</text>}
          {weeks.map((w, i) => {
            const bar = Math.min(24, step * 0.5), cx0 = x(i) + (step - bar) / 2;
            const parts: [number, string][] = [[w.rev_b_usage, "var(--color-rev-old)"], [w.rev_c_usage, "var(--color-rev-new)"], [w.shortage, "url(#unmet)"]];
            let base = bottom;
            return (
              <g key={w.week}>
                {parts.map(([value, fill], k) => {
                  if (!value) return null;
                  const h = demandY(value);
                  base -= h;
                  return <rect key={k} x={cx0} y={base} width={bar} height={Math.max(1, h - 1.5)} fill={fill} stroke={k === 2 ? "var(--color-critical)" : "none"} className="transition-all duration-300" />;
                })}
                {!narrow && <text x={x(i) + step / 2} y={base - 4} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={11} fill={w.shortage ? "var(--color-critical)" : "var(--color-ink-2)"}>{w.shortage ? `−${qty(w.shortage)}` : qty(w.demand)}</text>}
              </g>
            );
          })}
          <line x1={left} x2={width - right} y1={bottom} y2={bottom} stroke="var(--color-ink-2)" />
          <defs>
            <pattern id="stranded" width={7} height={7} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1={0} y1={0} x2={0} y2={7} stroke="var(--color-rev-old)" strokeWidth={1.2} opacity={0.55} />
            </pattern>
            <pattern id="unmet" width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width={6} height={6} fill="var(--color-critical-soft)" /><line x1={0} y1={0} x2={0} y2={6} stroke="var(--color-critical)" strokeWidth={2.5} />
            </pattern>
          </defs>
          {weeks.map((w, i) => (
            <text key={w.week} x={x(i) + step / 2} y={bottom + 17} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={12} fill="var(--color-ink-2)">W{w.week}</text>
          ))}
          {/* the two dates that define the transition */}
          <g>
            <line x1={boundary(useUpEnd + 1)} x2={boundary(useUpEnd + 1)} y1={18} y2={bottom} stroke="var(--color-rev-old)" strokeWidth={1.5} strokeDasharray="5 3" />
            <text x={boundary(useUpEnd + 1) - 5} y={13} textAnchor="end" fontSize={11.5} fontWeight={600} fill="var(--color-rev-old)">{narrow ? "Use-up" : `${oldRevision} use-up ends W${useUpEnd}`}</text>
            <line x1={boundary(effectiveWeek)} x2={boundary(effectiveWeek)} y1={18} y2={bottom} stroke="var(--color-rev-new)" strokeWidth={1.5} />
            <text x={boundary(effectiveWeek) + 5} y={13} fontSize={11.5} fontWeight={600} fill="var(--color-tech-strong)">{narrow ? "Effective" : `${newRevision} effective W${effectiveWeek}`}</text>
          </g>
          {weeks.map((w, i) => (
            <rect key={w.week} x={x(i)} y={0} width={step} height={height} fill="transparent" tabIndex={0} role="button"
              aria-label={`Week ${w.week}: demand ${qty(w.demand)}, unmet ${qty(w.shortage)}, ${oldRevision} closing ${qty(w.rev_b_closing)}, ${newRevision} closing ${qty(w.rev_c_closing)}`}
              onPointerMove={() => setActive(i)} onFocus={() => setActive(i)} onBlur={() => setActive(null)} />
          ))}
        </svg>
        {shown && active !== null && (
          <div role="status" className="pointer-events-none absolute top-8 z-10 w-52 rounded-sharp bg-navy-900 p-3 text-sm text-white shadow-menu"
            style={x(active) + step / 2 > width / 2 ? { right: Math.max(4, width - x(active) + 8) } : { left: Math.min(width - 212, x(active + 1) + 8) }}>
            <p className="mono mb-1 font-semibold">W{shown.week}</p>
            <dl className="num grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
              {([["Demand", shown.demand], ["Unmet", shown.shortage], [`${oldRevision} received`, shown.rev_b_receipts], [`${oldRevision} used`, shown.rev_b_usage],
                [`${oldRevision} closing`, shown.rev_b_closing], [`${newRevision} received`, shown.rev_c_receipts], [`${newRevision} used`, shown.rev_c_usage], [`${newRevision} closing`, shown.rev_c_closing]] as const).map(([k, v]) => (
                <div key={k} className="contents"><dt className="text-navy-300">{k}</dt><dd className="text-right font-semibold">{qty(v)}</dd></div>
              ))}
            </dl>
          </div>
        )}
      </div>
    </figure>
  );
}
