"use client";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Week } from "@/lib/api";
import { inr, qty } from "@/lib/format";

const LEGEND = { wrapperStyle: { fontSize: 13 }, iconSize: 12, formatter: (name: string) => <span style={{ color: "var(--color-ink-2)" }}>{name}</span> };
const AXIS = { tick: { fontSize: 12, fill: "var(--color-ink-2)", fontFamily: "var(--font-mono)" }, tickLine: false, axisLine: { stroke: "var(--color-line-strong)" } };

type TooltipItem = { name?: string | number; value?: number | string; color?: string; dataKey?: string | number };
function Readout({ active, payload, label, money }: { active?: boolean; payload?: TooltipItem[]; label?: string | number; money?: boolean }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-sharp bg-navy-900 p-3 text-sm text-white shadow-menu">
      <p className="mono mb-1 font-semibold">{label}</p>
      {payload.map((p) => (
        <p key={String(p.dataKey)} className="num flex items-center gap-2">
          <span aria-hidden className="h-0.5 w-3" style={{ background: p.color }} />
          <span className="font-semibold">{money ? inr(Number(p.value)) : qty(Number(p.value))}</span>
          <span className="text-navy-300">{p.name}</span>
        </p>
      ))}
    </div>
  );
}

type ChartProps = { weeks: Week[]; oldRevision: string; newRevision: string };

/** How each week's demand is covered. The bar's height is the demand. */
export function DemandCoverage({ weeks, oldRevision, newRevision }: ChartProps) {
  const data = weeks.map((w) => ({ week: `W${w.week}`, old: w.rev_b_usage, next: w.rev_c_usage, unmet: w.shortage }));
  return (
    <div className="h-72" role="img" aria-label="Demand per week, split into units covered by each revision and units not covered. The table below has every value.">
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <CartesianGrid vertical={false} stroke="var(--color-line)" />
          <XAxis dataKey="week" {...AXIS} />
          <YAxis {...AXIS} axisLine={false} width={52} />
          <Tooltip content={<Readout />} cursor={{ fill: "var(--color-neutral-soft)" }} />
          <Legend {...LEGEND} />
          <Bar dataKey="old" name={`${oldRevision} used`} stackId="d" fill="var(--color-rev-old)" maxBarSize={24} stroke="var(--color-sheet)" strokeWidth={1} />
          <Bar dataKey="next" name={`${newRevision} used`} stackId="d" fill="var(--color-rev-new)" maxBarSize={24} stroke="var(--color-sheet)" strokeWidth={1} />
          {weeks.some((w) => w.shortage > 0) && <Bar dataKey="unmet" name="Unmet demand" stackId="d" fill="var(--color-critical-soft)" stroke="var(--color-critical)" strokeWidth={1.5} maxBarSize={24} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Closing stock of both revisions against their protected safety stock. */
export function StockBalance({ weeks, oldRevision, newRevision }: ChartProps) {
  const data = weeks.map((w) => ({ week: `W${w.week}`, old: w.rev_b_closing, next: w.rev_c_closing, oldFloor: w.rev_b_safety_stock, nextFloor: w.rev_c_safety_stock }));
  return (
    <div className="h-72" role="img" aria-label="Closing stock per week for both revisions, with safety stock lines. The table below has every value.">
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <CartesianGrid vertical={false} stroke="var(--color-line)" />
          <XAxis dataKey="week" {...AXIS} />
          <YAxis {...AXIS} axisLine={false} width={52} />
          <Tooltip content={<Readout />} cursor={{ stroke: "var(--color-ink-3)" }} />
          <Legend {...LEGEND} />
          <Line type="linear" dataKey="oldFloor" name={`${oldRevision} safety stock`} stroke="var(--color-rev-old)" strokeWidth={1.5} strokeDasharray="2 4" dot={false} isAnimationActive={false} />
          <Line type="linear" dataKey="nextFloor" name={`${newRevision} safety stock`} stroke="var(--color-rev-new)" strokeWidth={1.5} strokeDasharray="2 4" dot={false} isAnimationActive={false} />
          <Line type="stepAfter" dataKey="old" name={`${oldRevision} closing`} stroke="var(--color-rev-old)" strokeWidth={2} dot={{ r: 4, fill: "var(--color-rev-old)", stroke: "var(--color-sheet)", strokeWidth: 2 }} isAnimationActive={false} />
          <Line type="stepAfter" dataKey="next" name={`${newRevision} closing`} stroke="var(--color-rev-new)" strokeWidth={2} dot={{ r: 4, fill: "var(--color-rev-new)", stroke: "var(--color-sheet)", strokeWidth: 2 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
