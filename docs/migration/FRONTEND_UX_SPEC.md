# Frontend UX specification

## Frame

* **Rail** (zones A to F). Entries a role cannot use are left out. On small screens it is a drawer.
* **Title block**: change, revisions, part, use-up and effective week, record check, next stage, data variant. A test variant turns the
  cell amber, adds a line that says it is not the current records, and hides the cells that describe the current records.
* **Go to** (Ctrl K) jumps to a page or change.

## Pages

| Route | The question it answers | Layout |
|---|---|---|
| `/dashboard` | What is changing, is production exposed, what may become excess, what is proposed, what needs a person? | Statement and next step; material flow with exposures; proposal beside exceptions; handover, actions, decisions |
| `/engineering-changes`, `/[id]` | Where does each change stand? | Table; then transition, record, record check, stock and orders, decision |
| `/ecn` | Which documents wait? | Intake (upload, paste, sample, by hand) beside the review list |
| `/ecn/[id]` | Is what was extracted what the document says? | Document with marked quotes beside the fields; each field shows found, missing, ambiguous, conflict, invalid or corrected |
| `/bom` | What does the change reach? | Wide lineage drawing, side panel, paths table |
| `/inventory` | What happens to the stock each week? | Full-width material flow with plan switch, results, balance, two charts, weekly records |
| `/optimization` | What does the engine propose and why? | Decision panel; evidence tabs: explanation, plans, rejected, robustness, baselines, run record |
| `/what-if` | What if something changes? | Question and interpreted parameters; baseline and earlier scenarios; comparison, two drawings, new exceptions, stress, explanation |
| `/exceptions` | What is worst? | Counts and filters beside the severity rail |
| `/approvals`, `/[run]` | Should this be approved? | Evidence first; decision stays in view on the right; confirmation repeats the plan |
| `/actions` | Who does what next? | Changes in progress, table, drawer with assignment, step and history |
| `/audit` | What happened, by whom? | Search, type filter, timeline by day, chain status, event drawer |
| `/replay` | Can the result be reproduced? | Runs, earlier replays, side-by-side verdict |
| `/settings` | Who am I, who may do what, is it running? | Profile, access (administrator), services |

## Rules

* The leading plan is prominent and says "Awaiting planner decision" until a person decides.
* The AI is a labelled text panel. It has no button that decides anything.
* No page sorts, ranks, sums costs or judges feasibility. Sums that are shown (`material_balance`) come from the backend.
* Loading, empty, error and refused states exist for every read and write. A failed write refreshes the page's data as well.
* A backend that is waking up is announced after five seconds.

## Responsive

Desktop first. From 1180 px the rail is a column. Below 1024 px it is a drawer. At 390 px sections stack, the title block keeps change,
revision and variant, tables scroll inside their frame, and drawings drop labels that no longer fit. Checked on every page by a test that
fails on horizontal overflow.
