# Frontend design system: the Engineering Transition Console

Source of truth: `frontend/styles/tokens.css` and `frontend/components/`. Reviewed in the running application with real engine data at
1440, 1180, 820 and 390 pixels.

## Concept

The product is a drawing sheet. Its border is the navigation, lettered like the zones of a drawing. Its title block is always visible and
always says which change is open. Its content is ruled, not boxed. Two revision triangles carry the identity: outlined bronze for the
revision that leaves, solid cyan for the revision that arrives. They mean the same thing in every place and are used for nothing else.

## Brand

* Name: ChangeWise AI. Descriptor: engineering change intelligence and phase-in/phase-out control.
* Mark: two overlapping revision triangles.
* Voice: short declarative sentences that start with the operational fact ("Production is covered in every week"). No promises. Every
  proposal is called a proposal.

## Colour

| Role | Token | Value |
|---|---|---|
| Structure | `navy-950` to `navy-100` | #0a1420 to #d8e2ec |
| Canvas, sheet, sunken | `canvas`, `sheet`, `sunken` | #efede5, #fbfaf6, #f5f3ec |
| Rules | `line`, `line-strong` | #d9d5c8, #a9a493 |
| Text | `ink`, `ink-2`, `ink-3` | #17212b, #46515c, #616b75 |
| Active operation | `tech`, `signal` (on navy) | #08708f, #3ccbee |
| Outgoing / incoming revision | `rev-old`, `rev-new` | #9a5b2e, #0a86a8 |
| Critical, high, pending, done | `critical`, `high`, `pending`, `done` | #a8261d, #b0480c, #8a5a00, #2b6e47 |

The revision pair was run through a palette validator on the sheet colour: lightness band, chroma, colour-vision separation (17.0 deutan,
22.6 tritan), normal-vision separation (21.2) and 3:1 contrast all pass. States always carry an icon and a word. Green appears only for
something validated, approved or done.

## Type

* Barlow for text, Barlow Condensed 600 for headings and large results, IBM Plex Mono for part numbers, weeks, run and plan IDs, hashes.
* Self-hosted through `@fontsource`; no request leaves the site.
* Hierarchy: page statement 36 to 48, page title 40 to 46, section 22, operational result 30 to 44, text 15, metadata 13.
* Columns of numbers use tabular figures; large single numbers do not.

## Space and shape

* Content width 1480, gutters 16 (phone) and 32. Sections are 48 apart and start with a 2 px rule.
* Corners 2 px. No shadows except on drawers and menus. No gradients. The drafting grid appears only behind drawings.

## Motion

One entrance of 260 ms, colour changes of 150 ms, chart geometry of 300 ms. `prefers-reduced-motion` removes all of it.

## Charts

* Hand-drawn SVG where the form is specific (Material Flow, BOM lineage, ribbon); Recharts for the two standard weekly charts; HTML for
  bars and the stress matrix.
* One axis per chart. Both stock lanes share a scale. Axes start at zero.
* Every week is a focusable column with a readout; every value is also in a table.
* Unmet demand is hatched red. Old stock that may no longer be used is hatched bronze. Stock is never drawn below zero.

## Own components

Revision Transition Ribbon, Material Flow Timeline, Inventory Balance (bar and charts), BOM Lineage Explorer, Optimization Decision Panel,
Exception Severity Rail, Decision Audit Timeline, Explainability Panel, Robustness Matrix, Title Block, Stage Track.

## Accessibility

Skip link, landmarks, one `h1` per page, labels on every field, native dialogs (focus trap and Escape), arrow keys in tabs, visible focus,
text contrast of at least 4.5:1, scrollable tables that take keyboard focus, no meaning by colour alone.
