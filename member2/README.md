# Member 2: constrained optimization and decision engine

Deterministic Python. No LLM is called and no number is hardcoded. Input and inventory simulation come
from Member 1 (`member1/`, through `integration/member1_bridge.py`); the result goes to Member 3.

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

**Member 1** supplies data and simulator. `integration/member1_bridge.py` translates names and units in both
directions and nothing else: `load_dataset(scenario)` gives the dataset of `contracts/input_schema.json`, and
`simulate_inventory(...)` calls `member1.engine.inventory`. Member 1's blocking validation findings (INVALID,
INSUFFICIENT_DATA) stop planning; NEEDS_REVIEW does not.

`reference/` is a **test double** (simulator and seeded scenarios) for unit tests and for escalation cases that
Member 1's data does not contain. Its reports are in `reports/seeded/`. Every result names the simulator that
produced it, and the planner rejects a simulator whose excess value does not match the official formula.

Bridge interpretations to confirm with Member 1: planning week = approval week; `cancel_allowed_until` also
limits reductions and deferrals; reductions come in steps of 50.

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
| Changeover | Either the effective week moves or (only with the test double) Rev B runs out to its use-up end; not both. Member 1's policy after the effective week is Rev C first, then Rev B |
| Effective week | May be at most one week after the use-up end; a longer gap has no permitted revision and is `INVALID_DATA`. Member 1 reports such a gap as NEEDS_REVIEW |
| Baseline B on Member 1's data | Switch right after the use-up end. In the base case that is the planned week, so A and B coincide |
| Blocked supplier | Keeping an undelivered order at a blocked supplier counts as a purchase; shipped orders are exempt |
| Alternate supplier | Cancels the original order, so its cancellation window and fee apply |
| Stress lead time | Delays undelivered Rev C orders only |
| Stress demand | Rounded to whole units; average demand D is recalculated from shocked demand |
| Deferral | No fee, because the official C has none |

## Findings worth discussing

- **Deck P1's expedite buys nothing.** The test double reproduces P1 / P2 / P3 exactly (₹37,000; ₹1,00,000;
  100 short); without the expedite P1 costs ₹25,000. On Member 1's data the best plan is the same reduction,
  PO-001 by 200, without any expedite: ₹17,000 against ₹92,000 for doing nothing.
- **The base case always goes to the planner.** Several ways to remove 200 Rev B units cost within ₹5,000.
- **The recommended base plan is fragile.** It survives 2 of 9 stress runs, and so do its near-tie rivals, so the
  robustness rule does not add an escalation.
- **A sturdier plan can lose quietly.** In `excess_rev_b_orders` the winner survives 2 of 9 and the next plan 4
  of 9, but they are not a near-tie, so the official rule stays silent.

## Known limits

- One plant, one change, whole units, weekly buckets. Fees are synthetic; no savings are claimed.
- OR-Tools needs its native library. Where the operating system blocks it, the engine uses PuLP and
  reports the OR-Tools check as `UNAVAILABLE` instead of passing it.
- Beyond `max_candidates` the solver returns up to `max_solutions` plans, so the full ranking and
  near-tie list cover only those.
