"use client";
import { useMemo, useState } from "react";
import type { BomImpact, BomNode } from "@/lib/api";
import { qty, words } from "@/lib/format";
import { Icon } from "@/components/ui/icons";
import { RevisionMark } from "@/components/engineering/RevisionMark";
import { Button, Facts, Status, cx } from "@/components/ui/primitives";

const TYPE: Record<string, string> = { FINISHED: "Finished product", ASSEMBLY: "Assembly", COMPONENT: "Component", KIT: "Service kit" };
const NODE_W = 208, NODE_H = 74, COL = 326, ROW = 100, PAD = 12;

type Placed = { node: BomNode; level: number; y: number };

/**
 * BOM Lineage Explorer. The changed component sits on the left; every step to the right is something that uses it.
 * Levels follow Member 1's where-used paths. A collapsed node hides what it is used in.
 */
export function LineageExplorer({ bom }: { bom: BomImpact }) {
  const [selected, setSelected] = useState(bom.old_material_id);
  const [collapsed, setCollapsed] = useState<string[]>([]);

  const parents = useMemo(() => {
    const map = new Map<string, string[]>();
    bom.edges.forEach((e) => map.set(e.child, [...(map.get(e.child) ?? []), e.parent]));
    return map;
  }, [bom]);

  const placed = useMemo(() => {
    const level = new Map<string, number>();
    // longest path from a changed component, so every user is drawn to the right of what it uses
    const visit = (id: string, depth: number, seen: string[]) => {
      if (seen.includes(id)) return; // cycles are reported by Member 1, not drawn
      level.set(id, Math.max(level.get(id) ?? 0, depth));
      if (!collapsed.includes(id)) (parents.get(id) ?? []).forEach((p) => visit(p, depth + 1, [...seen, id]));
    };
    [bom.old_material_id, bom.new_material_id].forEach((root) => visit(root, 0, []));
    const columns = new Map<number, BomNode[]>();
    bom.nodes.filter((n) => level.has(n.material_id)).forEach((n) => {
      const column = level.get(n.material_id)!;
      columns.set(column, [...(columns.get(column) ?? []), n]);
    });
    const tallest = Math.max(...[...columns.values()].map((c) => c.length));
    const result = new Map<string, Placed>();
    columns.forEach((nodes, column) => nodes.forEach((node, i) =>
      result.set(node.material_id, { node, level: column, y: PAD + (i + (tallest - nodes.length) / 2) * ROW })));
    return { map: result, width: columns.size * COL - (COL - NODE_W) + PAD * 2, height: tallest * ROW + PAD };
  }, [bom, parents, collapsed]);

  const onPath = useMemo(() => {
    const ids = new Set<string>();
    bom.paths.filter((p) => p.path_ids.includes(selected)).forEach((p) => p.path_ids.forEach((m) => ids.add(m)));
    ids.add(selected);
    return ids;
  }, [bom, selected]);

  const node = bom.nodes.find((n) => n.material_id === selected);
  const paths = bom.paths.filter((p) => p.path_ids.includes(selected));
  const x = (level: number) => PAD + level * COL;
  const toggle = (id: string) => setCollapsed((c) => (c.includes(id) ? c.filter((v) => v !== id) : [...c, id]));

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="drafting min-w-0 self-start overflow-auto border border-line bg-sheet" tabIndex={0} role="region" aria-label="Where-used lineage">
        <div className="relative m-4" style={{ width: placed.width, height: placed.height }}>
          <svg aria-hidden width={placed.width} height={placed.height} className="absolute inset-0">
            {bom.edges.map((e) => {
              const a = placed.map.get(e.child), b = placed.map.get(e.parent);
              if (!a || !b) return null;
              // several users of one parent enter it side by side, so their labels do not collide
              const siblings = bom.edges.filter((s) => s.parent === e.parent && placed.map.has(s.child));
              const entry = (siblings.indexOf(e) - (siblings.length - 1) / 2) * 34;
              const x1 = x(a.level) + NODE_W, y1 = a.y + NODE_H / 2, x2 = x(b.level), y2 = b.y + NODE_H / 2 + entry, mid = x1 + 26;
              const lit = onPath.has(e.child) && onPath.has(e.parent);
              return (
                <g key={`${e.child}-${e.parent}`}>
                  <path d={`M${x1},${y1} H${mid} V${y2} H${x2}`} fill="none" stroke={lit ? "var(--color-tech)" : "var(--color-line-strong)"} strokeWidth={lit ? 2.5 : 1.5} className="transition-colors" />
                  <text x={x2 - 8} y={y2 - 6} textAnchor="end" fontFamily="var(--font-mono)" fontSize={11.5} fill="var(--color-ink-2)">
                    {qty(e.quantity)} each{e.effective_to ? `, to W${e.effective_to}` : (e.effective_from ?? 1) > 1 ? `, from W${e.effective_from}` : ""}
                  </text>
                </g>
              );
            })}
          </svg>
          <ul>
            {[...placed.map.values()].map(({ node: n, level, y }) => {
              const changed = n.material_id === bom.old_material_id ? "old" : n.material_id === bom.new_material_id ? "new" : null;
              const users = parents.get(n.material_id)?.length ?? 0;
              return (
                <li key={n.material_id} className="absolute animate-enter" style={{ left: x(level), top: y, width: NODE_W, height: NODE_H }}>
                  <button type="button" onClick={() => setSelected(n.material_id)} aria-pressed={selected === n.material_id}
                    className={cx("flex size-full flex-col justify-center border bg-sheet px-3 text-left transition-colors",
                      n.type === "FINISHED" ? "border-double border-[3px]" : "border-[1.5px]",
                      selected === n.material_id ? "border-tech bg-tech-soft" : onPath.has(n.material_id) ? "border-ink" : "border-line-strong hover:border-ink")}>
                    <span className="flex items-center gap-2"><span className="mono font-semibold">{n.material_id}</span>{changed && <RevisionMark revision={n.revision} kind={changed} size={18} />}</span>{" "}
                    <span className="line-clamp-2 text-[13px] leading-tight text-ink-2">{n.name}</span>
                  </button>
                  {users > 0 && (
                    <button type="button" onClick={() => toggle(n.material_id)} aria-expanded={!collapsed.includes(n.material_id)}
                      aria-label={`${collapsed.includes(n.material_id) ? "Show" : "Hide"} what uses ${n.material_id}`}
                      className="absolute top-1/2 -right-3 flex size-6 -translate-y-1/2 items-center justify-center rounded-full border border-line-strong bg-sheet hover:border-ink">
                      <span className="mono text-sm leading-none">{collapsed.includes(n.material_id) ? "+" : "−"}</span>
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
      {node && (
        <aside aria-label="Selected material" className="space-y-5">
          <div>
            <p className="mono text-ink-2">{node.material_id}</p>
            <p className="display text-2xl">{node.name}</p>
          </div>
          <Facts columns={1} items={[["Kind", TYPE[node.type] ?? node.type], ["Revision", node.revision],
            ["Status", <Status key="s" tone={node.status === "Active" || node.status === "Released" ? "done" : "pending"}>{node.status}</Status>], ["Description", node.description ?? "Not recorded"]]} />
          <div>
            <h3 className="mb-2 text-sm font-semibold">Paths through this material</h3>
            {paths.length === 0 ? <p className="text-sm text-ink-2">Nothing above it is affected.</p> : (
              <ul className="space-y-2 text-sm">
                {paths.map((p) => (
                  <li key={p.path_ids.join()} className="border-l-2 border-line-strong pl-3">
                    <span className="mono flex flex-wrap items-center gap-1">
                      {[...p.path_ids].reverse().map((m, i) => <span key={m} className="inline-flex items-center gap-1">{i > 0 && <Icon name="arrow" size={12} />}{m}</span>)}
                    </span>
                    <span className="text-ink-2">{qty(p.quantity)} per {words(p.assembly_type ?? "assembly").toLowerCase()}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {collapsed.length > 0 && <Button onClick={() => setCollapsed([])}>Expand everything</Button>}
        </aside>
      )}
    </div>
  );
}
