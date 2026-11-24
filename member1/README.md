# ChangeWise AI: Member 1, Data Intelligence & Simulation Engine

Team TG10 · TECHgium 10th Edition · Pump Assembly mounting bracket **Rev B → Rev C**.

Python calculates, SQLite stores, Member 1 validates and simulates, Member 2 optimises, Member 3 explains, and the planner approves. All numbers are deterministic: identical inputs give an identical `simulation_id`.

## Setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv        # 3.11 per team spec; 3.13 also works
.venv\Scripts\Activate.ps1
$env:PYTHONPATH = ""          # stop packages from another folder leaking in
pip install -r requirements.txt
```

## Run

```powershell
python data/generate_synthetic.py            # write the 8 CSVs (deterministic)
python -m database.initialize_db             # build database/changewise.db (14 tables)
python documents/generate_ecn_samples.py     # 18 ECN PDFs + expected JSON + PyMuPDF check
python scripts/run_pipeline.py               # validate -> BOM impact -> simulate -> data/generated/
python scripts/evaluate_member1.py           # slide-8 metrics -> reports/member1_metrics.json
python -m pytest                             # 123 tests
streamlit run dashboard/inventory_view.py    # also bom_view.py, ecn_intake.py
```

## Use from Member 2 / Member 3

```python
from engine.data_loader import load_csv_data
from engine.inventory import simulate_from_data
from engine.validation import validate_all_inputs
from engine.bom_impact import generate_bom_impact_report
from engine.scenarios import load_scenario

data = load_csv_data()
result = simulate_from_data(data, "ECN-001", lead_time_shift=1, demand_multiplier=1.1)
result["total_shortage_units"], result["excess_value"], result["exceptions"]
```

The full contract (allocation policy, action-to-input mapping, result keys, open decisions) is in [reports/integration_contract.md](reports/integration_contract.md).

## Layout

| Path | What |
|---|---|
| `database/` | `schema.sql` (14 tables), `connection.py`, `initialize_db.py`, `changewise.db` |
| `data/synthetic/` | 8 input CSVs, from `data/generate_synthetic.py` |
| `data/generated/` | `simulation_results.csv`, `bom_impact.json`, `exceptions.json`, plus validation, scenario and full-result JSON |
| `documents/` | `ecn_samples/` (18 PDFs), `expected_outputs/` (18 ECN JSON + hand-checked `simulation_expected.json` + draft `severity_reference.json`), `manifest.json` |
| `engine/` | `validation`, `bom_impact`, `inventory` (simulator), `shortage`, `excess`, `severity`, `scenarios`, `metrics`, `data_loader` |
| `dashboard/` | Standalone Streamlit views: inventory, BOM, ECN intake |
| `tests/` | pytest suite |
| `reports/` | Data dictionary, database docs, validation report, integration contract, `member1_metrics.json` |
| `config/settings.yaml` | Engine version, horizon, 4-week cover, severity weights |

## Base-case result

S = 0 shortage units, E = ₹92,000 (230 Rev B units scrapped; Rev C within 4-week cover), status VALID. See [reports/member1_validation_report.md](reports/member1_validation_report.md).

## Changes from the original spec (so nobody is surprised)

* **Added a Rev C PO (PO-003, 500 units from S2, order W2 → arrival W6).** The spec had only Rev B POs, which would leave every plan 450 units short.
* Added columns: `engineering_changes.new_material_id` and `approval_week`; `purchase_orders.order_week`, `max_reduction_quantity` and `expedited`; `suppliers.expedited_lead_time_weeks` and `restriction_note`; `materials.material_type`.
* ECN field name `use_up_end_week` (the spec example says `use_up_end`).
* Rev B POs that arrive after the use-up end count as scrap, so deferring a PO cannot hide write-off.
