import type { Robustness } from "@/lib/api";
import { qty } from "@/lib/format";
import { Icon } from "@/components/ui/icons";
import { cx } from "@/components/ui/primitives";

const percent = (n: number) => (n === 0 ? "Planned demand" : `Demand ${n > 0 ? "+" : "−"}${Math.abs(Math.round(n * 100))}%`);

/** The nine stress runs. Each cell says what happens, not only whether it passed. */
export function RobustnessMatrix({ robustness, caption }: { robustness: Robustness; caption: string }) {
  const leads = [...new Set(robustness.scenarios.map((s) => s.lead_time_shock))];
  const demands = [...new Set(robustness.scenarios.map((s) => s.demand_shock))];
  return (
    <table className="w-full border-separate border-spacing-1 text-sm">
      <caption className="mb-1 text-left">
        <span className="display mr-2 text-2xl">{robustness.display}</span>
        <span className="text-ink-2">{caption}</span>
      </caption>
      <thead>
        <tr><td />{demands.map((d) => <th key={d} scope="col" className="px-1 text-left text-[13px] font-semibold text-ink-2">{percent(d)}</th>)}</tr>
      </thead>
      <tbody>
        {leads.map((lead) => (
          <tr key={lead}>
            <th scope="row" className="pr-2 text-left text-[13px] font-semibold text-ink-2">{lead === 0 ? "On time" : `${lead} wk late`}</th>
            {demands.map((demand) => {
              const run = robustness.scenarios.find((s) => s.lead_time_shock === lead && s.demand_shock === demand);
              return (
                <td key={demand} className={cx("h-12 px-2", run?.zero_shortage ? "bg-done-soft text-done" : "bg-critical-soft text-critical")}>
                  {run && (
                    <span className="flex items-center gap-1.5 font-semibold">
                      <Icon name={run.zero_shortage ? "check" : "alert"} size={14} />
                      {run.zero_shortage ? "Covered" : <span className="num">{qty(run.shortage_units)} short</span>}
                    </span>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
