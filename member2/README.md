# Member 2: constrained optimization and decision engine

Deterministic Python. No LLM is called and no number is hardcoded. Input comes from Member 1, the
result goes to Member 3.

## Run

From the repository root (Python 3.11 or newer):

```
python -m venv member2/.venv
member2/.venv/Scripts/python -m pip install -r member2/requirements.txt     # Windows
member2/.venv/Scripts/python -m pytest member2
member2/.venv/Scripts/python -m member2.evaluation.run_all                  # writes member2/reports
member2/.venv/Scripts/python -m streamlit run member2/dashboard/app.py
```

## How a run works

1. `constraints.input_errors`: bad data stops here (`INVALID_DATA`).
2. `action_generator`: one changeover option x one option per purchase order. Ineligible actions are
   recorded with reasons and kept as rejected single-action "probe" plans.
3. `planner`: hard rules first, then Member 1's simulator on an isolated copy.
4. `optimizer`: lexicographic `(S, E + C)`. Above `max_candidates`, `solver/` replaces enumeration.
5. `escalation`, `robustness`, `recommendation`: near-ties, nine stress runs, top three.

## Interfaces

**Member 1** supplies the dataset (`contracts/input_schema.json`; `engine/data_loader.py` reads SQLite
or JSON) and the simulator:

```python
simulate_inventory(materials, inventory, demand, purchase_orders, engineering_change)  # keyword args
```

The required return fields are under `$defs` in the input schema. `engineering_change` also carries
`consumption_policy` (`CUTOVER` or `RUN_OUT`). To switch to the real simulator, change one line in
`config/optimization.yaml`:

```yaml
simulator: member2.reference.simulator:simulate_inventory   # "module:function"
```

`reference/` is a **temporary stand-in** (simulator and synthetic scenarios) because Member 1's module
is not in the repository yet. Every result names the simulator that produced it, and the planner
rejects a simulator whose excess value does not match the official formula.

**Member 3** uses:

```python
from member2.engine.pipeline import run_optimization, evaluate_custom_plan, replay_matches
result = run_optimization(data)                 # contracts/output_schema.json
evaluate_custom_plan(actions, data)             # planner "modify"
replay_matches(result, data)                    # audit replay
```

What-if: change a copy of `data` and call `run_optimization` again. The Streamlit shell can import
`member2.dashboard.*_view.render(result)`. Member 1 and 3 metrics are read from a JSON file passed to
`run_all` (`{"metric_key": {"value": ..., "evidence": ...}}`); without it they show as `PENDING`.

## Decisions the team should confirm

| Topic | Implemented as |
| --- | --- |
| Near-tie boundary | Strict `<`; 5% **or** ₹5,000; percentage of the lower E + C; leader against each rival |
| Redundant variants | A plan that only adds a no-effect action (for example a free deferral) stays ranked but is not recommended and is not a near-tie rival. Switch: `skip_redundant_variants` |
| Changeover | Either the effective week moves (cutover) or Rev B runs out to its use-up end; not both |
| Effective week | Must not exceed the use-up end, matching the ECN date rule |
| Blocked supplier | Keeping an undelivered order at a blocked supplier counts as a purchase; shipped orders are exempt |
| Alternate supplier | Cancels the original order, so its cancellation window and fee apply |
| Stress lead time | Delays undelivered Rev C orders only |
| Stress demand | Rounded to whole units; average demand D is recalculated from shocked demand |
| Deferral | No fee, because the official C has none |

## Findings worth discussing

- **Deck P1 is not optimal.** The simulator reproduces P1 / P2 / P3 exactly (₹37,000; ₹1,00,000; 100
  short), but dropping P1's expedite gives the same stock result for ₹25,000, and the best plan found
  costs ₹1,250.
- **The ₹5,000 arm dominates cheap cases.** When good plans cost under ₹5,000 they are all near-ties,
  so the base case always goes to the planner.
- **A fragile plan can win quietly.** In `EXCESS_REV_B` the ₹26,000 plan survives 2 of 9 stress runs
  and the runner-up 9 of 9, but it is not a near-tie, so the official rule does not escalate.

## Known limits

- One plant, one change, whole units, weekly buckets. Fees are synthetic; no savings are claimed.
- OR-Tools needs its native library. Where the operating system blocks it, the engine uses PuLP and
  reports the OR-Tools check as `UNAVAILABLE` instead of passing it.
- Beyond `max_candidates` the solver returns up to `max_solutions` plans, so the full ranking and
  near-tie list cover only those.
