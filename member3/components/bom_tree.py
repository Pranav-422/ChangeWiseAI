import streamlit as st


def to_dot(impact):
    """Graphviz text of Member 1's where-used paths (no traversal here)."""
    def quote(name):
        return '"' + str(name).replace("\\", "").replace('"', "") + '"'
    lines = ["digraph {", "rankdir=BT;", 'node [shape=box, style="rounded,filled", fillcolor=white, fontname=Helvetica];',
             f'{quote(impact["material_id"])} [fillcolor="#fde7c7"];']
    lines += [f'{quote(a)} [fillcolor="#dbeafe"];' for a in impact["finished_assemblies"]]
    edges = {(p[i], p[i + 1]) for p in impact["paths"] for i in range(len(p) - 1)}
    return "\n".join(lines + [f"{quote(a)} -> {quote(b)};" for a, b in sorted(edges)] + ["}"])


def render(impact):
    st.graphviz_chart(to_dot(impact))
    st.caption("Orange: changed material. Blue: finished assemblies. Arrows point to where the part is used.")
