"use client";
import { LineageExplorer } from "@/components/bom/LineageExplorer";
import { useWorkspace } from "@/components/layout/Workspace";
import { Alert, Empty, Loaded, PageHeading, Section, TableFrame } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { qty, words } from "@/lib/format";
import { useData } from "@/lib/hooks";

export default function BomImpactPage() {
  const { change, scenario } = useWorkspace();
  const { data, error, mutate } = useData(["bom", change.change_id, scenario], () => api.bom(change.change_id, scenario));
  return (
    <Loaded data={data} error={error} retry={() => void mutate()}>
      {(bom) => (
        <>
          <PageHeading title="BOM impact" lead={bom.finished_products.length
            ? <>The change reaches <strong>{bom.finished_products.length}</strong> top-level products through <strong>{bom.direct_parents.length}</strong> direct parents.</>
            : "Nothing in the bill of materials uses the changed part."} />
          {bom.cycles.length > 0 && <div className="mb-6"><Alert kind="critical" title="The bill of materials has a cycle">{bom.cycles.map((c) => c.join(" uses ")).join("; ")}</Alert></div>}
          <div className="space-y-12">
            <Section title="Lineage" note="From the changed component on the left to everything that uses it. Select a material to see its paths.">
              {bom.nodes.length > 1 ? <LineageExplorer bom={bom} /> : <Empty title={words(bom.impact_status)} />}
            </Section>
            <Section title="Where-used paths">
              <TableFrame label="Where-used paths">
                <thead><tr><th>Changed material</th><th>Top-level product</th><th>Path</th><th>Quantity per product</th></tr></thead>
                <tbody>{bom.paths.map((p) => (
                  <tr key={p.path_ids.join()}><td className="mono">{p.material_id}</td><td><span className="mono">{p.assembly}</span> <span className="text-ink-2">{words(p.assembly_type)}</span></td>
                    <td className="mono">{[...p.path_ids].reverse().join("  →  ")}</td><td className="num">{qty(p.quantity)}</td></tr>
                ))}</tbody>
              </TableFrame>
            </Section>
          </div>
        </>
      )}
    </Loaded>
  );
}
