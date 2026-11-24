"""Compute Member 1's slide-8 metrics and write reports/member1_metrics.json.

Run from the member1 folder:  python scripts/evaluate_member1.py [predictions_dir]
predictions_dir (optional): a folder of ECN-0NN.json files from Member 3's extractor, each a flat
{field: value} object, scored for field-level extraction accuracy.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.data_loader import load_csv_data  # noqa: E402
from engine.inventory import simulate_from_data  # noqa: E402
from engine.metrics import ecn_field_accuracy, evaluate_all  # noqa: E402


def main(predictions_dir: str | None = None) -> dict:
    data = load_csv_data()
    m = evaluate_all(data)
    if predictions_dir:
        preds = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in Path(predictions_dir).glob("ECN-*.json")}
        m["ecn_field_accuracy"] = ecn_field_accuracy(preds)
    start, n = time.perf_counter(), 200
    for _ in range(n):
        simulate_from_data(data)
    m["simulation_speed_ms"] = round((time.perf_counter() - start) / n * 1000, 2)
    (ROOT / "reports" / "member1_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")

    b, r, s, a, k = (m["bom_impact_completeness"], m["inventory_reconciliation"], m["shortage_excess_detection"],
                     m["audit_replay"], m["severity_ranking_agreement"])
    print(f"BOM impact completeness      {b['completeness']:.0%}")
    print(f"Inventory reconciliation     {r['reconciled']}/{r['balances_checked']} balances over {r['runs']} runs")
    print(f"Shortage & excess detection  {s['exact_matches']}/{s['scenarios']} scenarios exact")
    print(f"Audit replay                 {a['identical']}/{a['replays']} identical")
    print(f"Severity ranking agreement   Kendall tau {k['kendall_tau']:.2f}, top-3 overlap {k['top3_overlap']:.0%} (reference is DRAFT)")
    if "ecn_field_accuracy" in m:
        print(f"ECN field accuracy           {m['ecn_field_accuracy']['accuracy']:.1%}")
    print(f"Simulation speed             {m['simulation_speed_ms']} ms per run")
    return m


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
