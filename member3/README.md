# Member 3: AI intelligence and application

**The engine calculates and decides. The AI reads and explains. The planner approves.** No authoritative
number, ranking, rule check or approval comes from an LLM.

## Run

From the repository root (Python 3.11 or newer). Member 3 imports Member 2, so both requirement files install:

```
python -m venv .venv
.venv/Scripts/python -m pip install -r member3/requirements.txt          # Windows
.venv/Scripts/python -m streamlit run member3/application/app.py
.venv/Scripts/python -m pytest member3
.venv/Scripts/python -m member3.evaluate                                 # writes member3/reports
```

Without an API key the app runs in demo mode: offline extraction rules and template explanations. To use
Gemini, copy `.env.example` to `.env` and set `GEMINI_API_KEY`. ECN text and engine facts are then sent to
Google. Another provider is one class and one entry in `ai/provider.py`.

## Demo path

ECN Intake: load sample 01, extract, tick the box, confirm, run planning. Then Optimization, What-If, Approval
Center (the base case is escalated, so a comment is required), Action Tracker, Audit History (replay). The
sidebar switches scenario and role.

## How untrusted AI output is contained

| Step | Control in code |
| --- | --- |
| ECN extraction | A value is kept only if its quote is in the document and the value is in the quote. Two values are a conflict, hedged text is ambiguous, unknown fields are dropped. Pydantic checks types, Member 1 checks master data, a human confirms |
| What-if | Strict schema, limits, and every number and identifier must be in the planner's question. Shown for confirmation first. Runs on a copy through Member 2 |
| Explanation | Amounts, units, weeks, plans, ranks, suppliers, orders, actions, robustness, approvals and promises are checked against engine facts. Missing warnings fail. A failed draft is stored but not shown |
| Labels | `AI-generated and verified`, `Template-generated`, `Awaiting review` |

## Integration

- **Member 1** through `services/member1_adapter.py`; its module name is `member1.module` in
  `config/settings.yaml`. `reference/member1_standin.py` is a **temporary stand-in** (data, ECN check, BOM,
  severity) because Member 1's module is not in the repository yet.
- **Member 2** through `services/member2_adapter.py`. Its dashboard views are reused, so numbers look the same.
- Metrics for Member 2's report:
  `python -m member2.evaluation.run_all member3/reports/evidence.json`.

Application records live in SQLite (`member3/data/app.db`, or `CHANGEWISE_DB`). The audit log is append-only
by trigger and hash-chained. State changes and their audit events commit in one transaction.

## Decisions the team should confirm

| Topic | Implemented as |
| --- | --- |
| ECN that differs from Member 1's change record | Blocked as `RECORD_MISMATCH` until corrected |
| All ten ECN fields | Required, including reason and approver |
| What-if Rev C delay | Moves open Rev C orders and lengthens their suppliers' lead times, so it cannot be expedited away |
| What-if effective week | Holds that week; other weeks are not offered |
| What-if order change | Only reductions of a Rev B order, priced and rule-checked by Member 2. Lifting a block is refused |
| Comments | Required for escalated cases, a lower-ranked plan, a modified plan and any rejection |
| Action owners | Purchasing for orders, Engineering for the effective week, Quality for using Rev B longer |

## Known limits

- **The LLM path has never run against a live model**: no key was available. It is tested with a fake provider.
- PDF text uses `pypdf` instead of the suggested PyMuPDF, whose native library Windows blocked on the
  development PC. Scanned PDFs have no text layer, so they are refused; there is no OCR.
- Roles are chosen in the sidebar. There is no login, so the audit log records a claimed name.
- The hash chain detects edits, gaps and reordering, but not removal of the newest events.
- The claim verifier is pattern-based. It is tuned to reject or hold back wording it cannot check, so some
  true sentences fall back to the template.
- The extraction samples were written together with the offline rules; their accuracy says little about real
  documents.
