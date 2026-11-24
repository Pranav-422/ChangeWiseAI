# Known issues and open decisions

## Business rules the team has not confirmed (kept as implemented)

1. Near-tie: "5% or Rs 5,000" is read as either test; boundaries are strict; the percentage uses the lower of the two values.
2. `planning_week` is the approval week, and `cancel_allowed_until` is also the deadline for reducing or deferring an order.
3. Orders are reduced in steps of 50 units.
4. Safety stock is a protected floor for production (Member 1's policy).
5. `D` in the Rev C excess formula is the average demand over the horizon.

## Differences that can surprise

* The base plan covers demand in 2 of 9 stress runs. Every near-tie alternative has the same 2/9, so no robustness escalation is raised.
* Member 1's scenario variants are test variants of one change. The interface labels them "Test variant" and shows that they are not the
  current records.
* Explanations are stored with the run. An explanation written before the decision still says that nothing is approved; "Explain again"
  writes a new one.

## Technical limits

* **Audit chain.** It detects changes inside the log. It cannot detect that the newest events were cut off, or a complete rewrite by a
  database administrator who also disables the triggers. The page shows the latest hash so it can be kept elsewhere.
* **Scanned PDFs** without a text layer are refused. No OCR is included.
* **Claim verifier** is deterministic and conservative: a true sentence it cannot check leads to the template.
* **Writers are serialised** by one advisory lock, as SQLite did. Enough for a planning team, not for hundreds of concurrent writers.
* **No rate limit** in the API. Supabase limits sign-in attempts; the API relies on authentication and on body limits.
* **Render free plan** sleeps after 15 minutes; the first request then takes about a minute. The interface says so and waits.
* **CSP** allows inline scripts, because Next.js injects its bootstrap inline.
* **Python 3.11** is not tested; 3.12 is.
* **PyMuPDF** is blocked by an Application Control policy on one development computer, so three Member 1 tests fail there. They run in CI.
