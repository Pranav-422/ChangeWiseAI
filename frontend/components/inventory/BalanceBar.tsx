import type { Inventory } from "@/lib/api";
import { qty } from "@/lib/format";

/** Where the outgoing revision's supply goes: used, held for service, or left over. One whole, three parts. */
export function BalanceBar({ balance, revision }: { balance: NonNullable<Inventory["material_balance"]>; revision: string }) {
  const total = balance.opening + balance.receipts;
  const parts = [
    { name: "Used in production", value: balance.used, style: "bg-rev-old text-white" },
    { name: "Held for service", value: balance.reserved, style: "bg-line-strong text-ink" },
    { name: "Left over", value: balance.scrap, style: "hatch border border-pending text-pending" },
  ];
  return (
    <figure aria-label={`${revision} supply of ${qty(total)} units: ${parts.map((p) => `${p.name} ${qty(p.value)}`).join(", ")}`}>
      <div className="flex h-7 gap-0.5">
        {parts.map((p) => p.value > 0 && <div key={p.name} title={`${p.name}: ${qty(p.value)}`} style={{ flexGrow: p.value }} className={`rounded-soft ${p.style}`} />)}
      </div>
      <figcaption className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {parts.map((p) => (
          <span key={p.name} className="inline-flex items-center gap-1.5"><span aria-hidden className={`size-3 ${p.style}`} /><span className="num font-semibold">{qty(p.value)}</span><span className="text-ink-2">{p.name}</span></span>
        ))}
        <span className="text-ink-2">of {qty(total)} ({qty(balance.opening)} on hand, {qty(balance.receipts)} on order)</span>
      </figcaption>
    </figure>
  );
}
