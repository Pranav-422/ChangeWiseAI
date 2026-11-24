"""End-to-end Member 1 run: rebuild DB -> validate -> BOM impact -> simulate -> store -> write data/generated/.

Run from the member1 folder:  python scripts/run_pipeline.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.connection import get_connection  # noqa: E402
from database.initialize_db import initialize_database  # noqa: E402
from engine.bom_impact import generate_bom_impact_report  # noqa: E402
from engine.data_loader import load_data_from_db, save_simulation_run, to_records  # noqa: E402
from engine.inventory import calculate_closing_stock, simulate_from_data  # noqa: E402
from engine.scenarios import SCENARIOS, load_scenario  # noqa: E402
from engine.validation import validate_all_inputs  # noqa: E402

OUT = ROOT / "data" / "generated"


def main(change_id: str = "ECN-001") -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    counts = initialize_database()
    conn = get_connection()
    try:
        data = load_data_from_db(conn)
        change = next((c for c in to_records(data["engineering_changes"]) if c["change_id"] == change_id), None)
        if change is None:
            raise SystemExit(f"Engineering change {change_id} not found in the database")
        validation = validate_all_inputs(data, change_id)
        bom = generate_bom_impact_report(change["part_number"], data["bom"], data["materials"], change)
        sim = simulate_from_data(data, change_id)
        save_simulation_run(conn, sim)
        scenarios = []
        for name in SCENARIOS:
            s = simulate_from_data(load_scenario(name, data), change_id, scenario_id=name.upper())
            scenarios.append({"scenario_id": s["scenario_id"], "description": SCENARIOS[name],
                              "simulation_id": s["simulation_id"], "validation_status": s["validation_status"],
                              "total_shortage_units": s["total_shortage_units"],
                              "first_shortage_week": (s["shortage"] or {}).get("first_shortage_week"),
                              "excess_value": s["excess_value"],
                              "top_exception": s["exceptions"][0]["exception_id"] if s["exceptions"] else None})
    finally:
        conn.close()

    import pandas as pd
    pd.DataFrame(sim["weeks"]).to_csv(OUT / "simulation_results.csv", index=False, lineterminator="\n")
    (OUT / "bom_impact.json").write_text(json.dumps(bom, indent=2), encoding="utf-8")
    (OUT / "exceptions.json").write_text(json.dumps(sim["exceptions"], indent=2), encoding="utf-8")
    (OUT / "validation_result.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    (OUT / "simulation_result.json").write_text(json.dumps(sim, indent=2), encoding="utf-8")
    (OUT / "scenario_summary.json").write_text(json.dumps(scenarios, indent=2), encoding="utf-8")

    reconciled = all(r["rev_b_reconciled"] and r["rev_c_reconciled"] for r in calculate_closing_stock(sim))
    print(f"DB tables: {len(counts)}  | input rows: {sum(counts.values())}")
    print(f"Validation: {validation['status']}  | BOM impact: {bom['impact_status']} "
          f"({len(bom['affected_assemblies'])} paths, finished: {bom['affected_finished_products']})")
    print(f"Simulation {sim['simulation_id']}: {sim['validation_status']}  shortage={sim['total_shortage_units']}  "
          f"E={sim['excess_value']:,.0f}  reconciled={reconciled}")
    for s in scenarios:
        print(f"  {s['scenario_id']:22s} {s['validation_status']:18s} S={s['total_shortage_units']:>4}  "
              f"E={s['excess_value']:>10,.0f}  top={s['top_exception']}")
    return {"validation": validation, "bom": bom, "simulation": sim, "scenarios": scenarios}


if __name__ == "__main__":
    main()
