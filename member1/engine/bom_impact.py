"""Reverse (where-used) BOM traversal: which assemblies and finished products use a changed component."""
from collections import defaultdict

from .data_loader import as_num, to_records


def _parents_map(bom) -> dict[str, list[dict]]:
    parents = defaultdict(list)
    for r in to_records(bom):
        parents[r["child_material_id"]].append(r)
    return parents


def find_bom_cycles(bom) -> list[list[str]]:
    """Every cycle in the parent->child graph, each as [a, b, ..., a]."""
    children = defaultdict(set)
    for r in to_records(bom):
        children[r["parent_material_id"]].add(r["child_material_id"])
    cycles, state, stack = [], {}, []

    def dfs(node):
        state[node] = 1
        stack.append(node)
        for child in sorted(children[node]):
            if state.get(child) == 1:
                cycles.append(stack[stack.index(child):] + [child])
            elif child not in state:
                dfs(child)
        stack.pop()
        state[node] = 2

    for node in sorted(children):
        if node not in state:
            dfs(node)
    return cycles


def get_parent_materials(material_id: str, bom) -> list[str]:
    """Direct parents (one level up)."""
    return sorted({r["parent_material_id"] for r in _parents_map(bom).get(material_id, [])})


def trace_where_used(material_id: str, bom) -> dict:
    """All upward paths from the material to each top-level parent.

    Returns {"paths": [{"ids": [top, ..., material], "quantity": units of material per top unit}],
             "cycles": [[...]]}. A path stops where it would revisit a node, so cycles cannot loop forever.
    """
    parents = _parents_map(bom)
    paths, cycles = [], []

    def walk(node, chain, qty):          # chain runs material -> ... -> node
        ups = parents.get(node, [])
        if not ups:
            if len(chain) > 1:
                paths.append({"ids": chain[::-1], "quantity": qty})
            return
        for r in sorted(ups, key=lambda r: r["parent_material_id"]):
            p = r["parent_material_id"]
            if p in chain:
                cycles.append(chain[chain.index(p):][::-1] + [p])  # reported top-down
                continue
            walk(p, chain + [p], qty * (as_num(r["quantity_per_parent"]) or 0))

    walk(material_id, [material_id], 1.0)
    return {"paths": paths, "cycles": cycles}


def get_affected_assemblies(material_id: str, bom) -> dict:
    """Direct parents, indirect parents and top-level (finished) products that use the material."""
    trace = trace_where_used(material_id, bom)
    direct = get_parent_materials(material_id, bom)
    every = {m for p in trace["paths"] for m in p["ids"][:-1]}
    # Parents that sit on a cycle never reach a top-level node; still count them as affected.
    every |= {m for c in trace["cycles"] for m in c if m != material_id}
    return {
        "direct_parents": direct,
        "indirect_parents": sorted(every - set(direct)),
        "top_level_products": sorted({p["ids"][0] for p in trace["paths"]}),
        "paths": trace["paths"],
        "cycles": trace["cycles"],
    }


def generate_bom_impact_report(material_id: str, bom, materials=None, change: dict | None = None) -> dict:
    """JSON-ready impact report. Status: IDENTIFIED | NO_WHERE_USED | CYCLE_DETECTED | MATERIAL_NOT_FOUND."""
    mats = {m["material_id"]: m for m in to_records(materials)}
    name = lambda mid: mats.get(mid, {}).get("material_name", mid)   # noqa: E731
    report = {
        "material": material_id,
        "material_name": name(material_id),
        "old_revision": mats.get(material_id, {}).get("revision"),
        "new_material": (change or {}).get("new_material_id"),
        "new_revision": (change or {}).get("new_revision"),
        "change_id": (change or {}).get("change_id"),
    }
    if mats and material_id not in mats:
        return {**report, "affected_assemblies": [], "direct_parents": [], "indirect_parents": [],
                "affected_finished_products": [], "cycles": [], "impact_status": "MATERIAL_NOT_FOUND"}
    a = get_affected_assemblies(material_id, bom)
    report.update(
        affected_assemblies=[{
            "assembly": p["ids"][0],
            "assembly_type": mats.get(p["ids"][0], {}).get("material_type"),
            "path": [name(m) for m in p["ids"]],
            "path_ids": p["ids"],
            "quantity_per_assembly": p["quantity"],
        } for p in a["paths"]],
        direct_parents=a["direct_parents"],
        indirect_parents=a["indirect_parents"],
        affected_finished_products=a["top_level_products"],
        cycles=a["cycles"],
        impact_status="CYCLE_DETECTED" if a["cycles"] else "IDENTIFIED" if a["paths"] else "NO_WHERE_USED",
    )
    return report
