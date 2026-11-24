"""Input validation. Every check returns machine-readable issues; nothing is silently defaulted.

Outcome statuses, worst first:
  INVALID            core data is wrong; planning must stop
  INSUFFICIENT_DATA  essential information is missing; a human must supply it
  NEEDS_REVIEW       planning can run, but a human must confirm (e.g. a restricted supplier on an affected PO
                     invalidates sourcing actions on that PO, not the whole change)
  VALID              no blocking issue (INFO issues may still be listed)
"""
import re
from enum import Enum

from pydantic import BaseModel

from .bom_impact import find_bom_cycles
from .data_loader import as_int, as_num, to_records


class Status(str, Enum):
    VALID = "VALID"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID = "INVALID"


_RANK = {Status.VALID: 0, Status.NEEDS_REVIEW: 1, Status.INSUFFICIENT_DATA: 2, Status.INVALID: 3}
_SEVERITY = {Status.INVALID: "ERROR", Status.INSUFFICIENT_DATA: "ERROR", Status.NEEDS_REVIEW: "WARNING",
             Status.VALID: "INFO"}

REVISION_RE = re.compile(r"^Rev [A-Z]$")
MAX_CALENDAR_WEEK = 52
MATERIAL_STATUSES = {"Active", "Released", "Phase-Out", "Obsolete", "Blocked"}
SUPPLIER_STATUSES = {"Approved", "Blocked", "Unqualified"}
RECEIVABLE_PO_STATUSES = {"Open", "Confirmed"}
PO_STATUSES = RECEIVABLE_PO_STATUSES | {"Cancelled", "Received"}
REQUIRED_CHANGE_FIELDS = ("change_id", "part_number", "new_material_id", "old_revision", "new_revision",
                          "effective_week", "use_up_end_week", "interchangeability")


class ValidationIssue(BaseModel):
    code: str
    status: Status
    severity: str          # ERROR | WARNING | INFO
    record: str            # affected record, e.g. "PO-003" or "ECN-001.effective_week"
    description: str
    resolution: str        # recommended resolution
    week: int | None = None


class ValidationResult(BaseModel):
    scope: str
    status: Status
    issues: list[ValidationIssue] = []

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


def worst_status(statuses) -> Status:
    return max(statuses, key=_RANK.get, default=Status.VALID)


def issue(code, status, record, description, resolution, week=None) -> ValidationIssue:
    return ValidationIssue(code=code, status=status, severity=_SEVERITY[status], record=str(record),
                           description=description, resolution=resolution, week=week)


def _result(scope, issues) -> ValidationResult:
    return ValidationResult(scope=scope, status=worst_status(i.status for i in issues), issues=issues)


def _missing(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def validate_engineering_change(change: dict, materials) -> ValidationResult:
    mats = {m["material_id"]: m for m in to_records(materials)}
    cid = change.get("change_id") or "<no change_id>"
    out = [issue("ECN_MISSING_FIELD", Status.INSUFFICIENT_DATA, f"{cid}.{f}",
                 f"Required field '{f}' is missing and is not defaulted.",
                 f"Confirm '{f}' with Engineering and resubmit the change.")
           for f in REQUIRED_CHANGE_FIELDS if _missing(change.get(f))]
    part, new_id = change.get("part_number"), change.get("new_material_id")
    old_rev, new_rev = change.get("old_revision"), change.get("new_revision")

    if not _missing(part):
        if part not in mats:
            out.append(issue("ECN_UNKNOWN_PART", Status.INVALID, f"{cid}.part_number",
                             f"Part {part} is not in the material master.", "Correct the part number."))
        elif not _missing(old_rev) and mats[part]["revision"] != old_rev:
            out.append(issue("ECN_OLD_REVISION_MISMATCH", Status.INVALID, f"{cid}.old_revision",
                             f"ECN says {part} is {old_rev}; material master says {mats[part]['revision']}.",
                             "Reconcile the ECN with the material master."))
    if not _missing(new_rev):
        if not REVISION_RE.match(str(new_rev)):
            out.append(issue("ECN_INVALID_REVISION_FORMAT", Status.INVALID, f"{cid}.new_revision",
                             f"New revision '{new_rev}' is not of the form 'Rev X'.", "Correct the revision."))
        elif new_rev == old_rev:
            out.append(issue("ECN_REVISION_UNCHANGED", Status.INVALID, f"{cid}.new_revision",
                             "Old and new revision are identical.", "Correct the revisions."))
    if not _missing(new_id):
        if new_id not in mats:
            out.append(issue("ECN_UNKNOWN_NEW_MATERIAL", Status.INVALID, f"{cid}.new_material_id",
                             f"New material {new_id} is not in the material master.",
                             "Create the new-revision material record first."))
        elif new_id == part:
            out.append(issue("ECN_SAME_MATERIAL", Status.INVALID, f"{cid}.new_material_id",
                             "Old and new material IDs are the same.", "Correct the new material ID."))
        elif not _missing(new_rev) and mats[new_id]["revision"] != new_rev:
            out.append(issue("ECN_NEW_REVISION_MISMATCH", Status.INVALID, f"{cid}.new_revision",
                             f"ECN says {new_id} is {new_rev}; material master says {mats[new_id]['revision']}.",
                             "Reconcile the ECN with the material master."))

    weeks = {}
    for f, code in (("effective_week", "ECN_INVALID_EFFECTIVE_WEEK"), ("use_up_end_week", "ECN_INVALID_USE_UP_WEEK")):
        if _missing(change.get(f)):
            continue
        w = as_int(change[f])
        if w is None or not 1 <= w <= MAX_CALENDAR_WEEK:
            out.append(issue(code, Status.INVALID, f"{cid}.{f}",
                             f"{f} = {change[f]!r} is not a week number between 1 and {MAX_CALENDAR_WEEK}.",
                             "Enter a valid week (W1 = 1)."))
        else:
            weeks[f] = w
    inter = change.get("interchangeability")
    inter_ok = not _missing(inter) and inter in (True, False)   # also accepts 0 / 1
    if not _missing(inter) and not inter_ok:
        out.append(issue("ECN_INVALID_INTERCHANGEABILITY", Status.INVALID, f"{cid}.interchangeability",
                         f"Interchangeability {inter!r} must be true or false.", "Confirm with Engineering."))
    if len(weeks) == 2 and inter_ok:
        eff, use = weeks["effective_week"], weeks["use_up_end_week"]
        if use < eff - 1:
            out.append(issue("ECN_REVISION_GAP", Status.NEEDS_REVIEW, cid,
                             f"No revision is permitted in W{use + 1}-W{eff - 1}: old revision ends W{use}, "
                             f"new revision starts W{eff}.", "Align the use-up end and effective week."))
        elif use >= eff and not bool(inter):
            out.append(issue("ECN_USE_UP_AFTER_EFFECTIVE", Status.NEEDS_REVIEW, cid,
                             f"Use-up end W{use} is at/after effective week W{eff}, but the revisions are not "
                             f"interchangeable, so the old revision cannot be used from W{eff}.",
                             "Confirm the use-up end date with Engineering."))
    status = change.get("approval_status")
    if not _missing(status) and status != "Approved":
        out.append(issue("ECN_NOT_APPROVED", Status.NEEDS_REVIEW, f"{cid}.approval_status",
                         f"Change status is '{status}', not Approved.", "Plan only after approval."))
    return _result("engineering_change", out)


def validate_materials(materials) -> ValidationResult:
    out, seen = [], set()
    for m in to_records(materials):
        mid = m.get("material_id")
        if _missing(mid):
            out.append(issue("MAT_MISSING_ID", Status.INVALID, "<material>", "Material without an ID.", "Add the ID."))
            continue
        if mid in seen:
            out.append(issue("MAT_DUPLICATE_ID", Status.INVALID, mid, f"Material ID {mid} appears more than once.",
                             "Keep one record per material ID."))
        seen.add(mid)
        if _missing(m.get("revision")) or not REVISION_RE.match(str(m["revision"])):
            out.append(issue("MAT_INVALID_REVISION", Status.INVALID, mid, f"Revision {m.get('revision')!r} is not 'Rev X'.",
                             "Correct the revision."))
        cost = as_num(m.get("unit_cost"))
        if cost is None or cost < 0:
            out.append(issue("MAT_INVALID_UNIT_COST", Status.INVALID, mid, f"Unit cost {m.get('unit_cost')!r} is invalid.",
                             "Enter a non-negative unit cost."))
        if m.get("material_status") not in MATERIAL_STATUSES:
            out.append(issue("MAT_UNKNOWN_STATUS", Status.INVALID, mid, f"Status {m.get('material_status')!r} is not recognised.",
                             f"Use one of {sorted(MATERIAL_STATUSES)}."))
    return _result("materials", out)


def validate_inventory(inventory, materials=None) -> ValidationResult:
    known = {m["material_id"] for m in to_records(materials)} if materials is not None else None
    out = []
    for r in to_records(inventory):
        rid = r.get("inventory_id") or r.get("material_id")
        if known is not None and r.get("material_id") not in known:
            out.append(issue("INV_UNKNOWN_MATERIAL", Status.INVALID, rid, f"Material {r.get('material_id')} is not in the material master.",
                             "Fix the material ID."))
        vals = {}
        for f in ("on_hand", "reserved", "safety_stock"):
            v = as_num(r.get(f))
            if v is None or v < 0:
                out.append(issue("INV_INVALID_QUANTITY", Status.INVALID, rid, f"{f} = {r.get(f)!r} must be a number >= 0.",
                                 "Correct the stock record."))
            vals[f] = v
        if vals["on_hand"] is not None and vals["reserved"] is not None and vals["reserved"] > vals["on_hand"]:
            out.append(issue("INV_RESERVED_EXCEEDS_ON_HAND", Status.INVALID, rid,
                             f"Reserved {vals['reserved']:.0f} exceeds on-hand {vals['on_hand']:.0f} (data-quality error).",
                             "Reconcile reservations with physical stock."))
    return _result("inventory", out)


def validate_bom(bom, materials) -> ValidationResult:
    known = {m["material_id"] for m in to_records(materials)}
    out, seen = [], {}
    for r in to_records(bom):
        rid = r.get("bom_id") or f"{r.get('parent_material_id')}->{r.get('child_material_id')}"
        for f in ("parent_material_id", "child_material_id"):
            if r.get(f) not in known:
                out.append(issue("BOM_UNKNOWN_MATERIAL", Status.INVALID, rid, f"{f} {r.get(f)} is not in the material master.",
                                 "Fix the BOM reference."))
        qty = as_num(r.get("quantity_per_parent"))
        if qty is None or qty <= 0:
            out.append(issue("BOM_INVALID_QUANTITY", Status.INVALID, rid, f"Quantity per parent {r.get('quantity_per_parent')!r} must be > 0.",
                             "Correct the quantity."))
        key = (r.get("parent_material_id"), r.get("child_material_id"), as_int(r.get("effective_from")))
        if key in seen:
            out.append(issue("BOM_DUPLICATE_RELATIONSHIP", Status.INVALID, rid, f"Duplicates {seen[key]} ({key[0]} -> {key[1]}).",
                             "Remove the duplicate BOM line."))
        seen.setdefault(key, rid)
    for cycle in find_bom_cycles(bom):
        out.append(issue("BOM_CYCLE", Status.INVALID, " -> ".join(cycle), "Circular BOM relationship.",
                         "Break the cycle in the BOM."))
    return _result("bom", out)


def validate_suppliers(suppliers) -> ValidationResult:
    out = []
    for s in to_records(suppliers):
        sid, status = s.get("supplier_id"), s.get("supplier_status")
        if status not in SUPPLIER_STATUSES:
            out.append(issue("SUP_UNKNOWN_STATUS", Status.INVALID, sid, f"Status {status!r} is not Approved/Blocked/Unqualified.",
                             "Set an explicit supplier status."))
        lead = s.get("lead_time_weeks")
        if lead is None:
            out.append(issue("SUP_MISSING_LEAD_TIME", Status.NEEDS_REVIEW, sid, "Lead time is missing.",
                             "Obtain the lead time from Purchasing."))
        elif as_int(lead) is None or as_int(lead) < 0:
            out.append(issue("SUP_INVALID_LEAD_TIME", Status.INVALID, sid, f"Lead time {lead!r} must be a whole number >= 0.",
                             "Correct the lead time."))
        if status in ("Blocked", "Unqualified"):
            if _missing(s.get("restriction_note")):
                out.append(issue("SUP_RESTRICTION_NOT_EXPLICIT", Status.NEEDS_REVIEW, sid,
                                 f"{status} supplier has no restriction reason.", "Record why the supplier is restricted."))
            else:
                out.append(issue("SUP_RESTRICTED", Status.VALID, sid, f"{status}: {s['restriction_note']}",
                                 "Do not source from this supplier."))
        if bool(s.get("expedite_available")):
            exp = as_int(s.get("expedited_lead_time_weeks"))
            if exp is None or exp < 0 or (as_int(lead) is not None and exp > as_int(lead)):
                out.append(issue("SUP_INVALID_EXPEDITE_LEAD_TIME", Status.NEEDS_REVIEW, sid,
                                 "Expedite is offered but the expedited lead time is missing or longer than normal.",
                                 "Confirm the expedited lead time."))
    return _result("suppliers", out)


def validate_purchase_orders(pos, suppliers, groups, affected_materials=None) -> ValidationResult:
    """`affected_materials`: materials of the change. Restricted suppliers on other materials are INFO only."""
    sups = {s["supplier_id"]: s for s in to_records(suppliers)}
    grps = to_records(groups)
    group_ids = {g["group_id"] for g in grps}
    auth = {(g["group_id"], g["material_id"], g["supplier_id"]): g["authorization_status"] for g in grps}
    out, seen = [], set()
    for po in to_records(pos):
        pid = po.get("po_id")
        if pid in seen:
            out.append(issue("PO_DUPLICATE_ID", Status.INVALID, pid, "PO ID appears more than once.", "Keep one record per PO."))
        seen.add(pid)
        receivable = po.get("po_status") in RECEIVABLE_PO_STATUSES
        if po.get("po_status") not in PO_STATUSES:
            out.append(issue("PO_UNKNOWN_STATUS", Status.INVALID, pid, f"Status {po.get('po_status')!r} is not recognised.",
                             f"Use one of {sorted(PO_STATUSES)}."))
        qty = as_int(po.get("quantity"))
        if qty is None or qty < 0:
            out.append(issue("PO_INVALID_QUANTITY", Status.INVALID, pid, f"Quantity {po.get('quantity')!r} must be a whole number >= 0.",
                             "Correct the PO quantity."))
        elif qty == 0 and receivable:
            out.append(issue("PO_ZERO_QUANTITY", Status.NEEDS_REVIEW, pid, "Open PO with zero quantity.", "Close or correct the PO."))
        arrival = as_int(po.get("arrival_week"))
        if arrival is None or arrival < 1:
            out.append(issue("PO_INVALID_ARRIVAL_WEEK", Status.INVALID, pid, f"Arrival week {po.get('arrival_week')!r} must be >= 1.",
                             "Correct the arrival week."))
        cancel = po.get("cancel_allowed_until")
        if cancel is not None and (as_int(cancel) is None or (arrival is not None and as_int(cancel) > arrival)):
            out.append(issue("PO_INVALID_CANCEL_WINDOW", Status.INVALID, pid,
                             f"Cancel-allowed-until {cancel!r} is not a week on or before arrival W{arrival}.",
                             "Correct the cancellation window."))
        if as_int(po.get("maximum_defer_weeks")) is None or as_int(po.get("maximum_defer_weeks")) < 0:
            out.append(issue("PO_INVALID_DEFER_LIMIT", Status.INVALID, pid, "Maximum defer weeks must be a whole number >= 0.",
                             "Correct the deferral limit."))
        for fee in ("cancellation_fee", "reduction_fee", "expedite_fee"):
            if fee in po and (as_num(po[fee]) is None or as_num(po[fee]) < 0):
                out.append(issue("PO_INVALID_FEE", Status.INVALID, pid, f"{fee} {po[fee]!r} must be >= 0.", "Correct the fee."))
        sup = sups.get(po.get("supplier_id"))
        if sup is None:
            out.append(issue("PO_UNKNOWN_SUPPLIER", Status.INVALID, pid, f"Supplier {po.get('supplier_id')} does not exist.",
                             "Fix the supplier reference."))
        group = po.get("purchasing_group")
        if group not in group_ids:
            out.append(issue("PO_UNKNOWN_PURCHASING_GROUP", Status.INVALID, pid, f"Purchasing group {group!r} is not recognised.",
                             "Assign a valid purchasing group."))
        elif auth.get((group, po.get("material_id"), po.get("supplier_id"))) != "Authorized":
            out.append(issue("PO_GROUP_NOT_AUTHORIZED", Status.NEEDS_REVIEW, pid,
                             f"Group {group} is not authorized for {po.get('material_id')} from {po.get('supplier_id')}.",
                             "Route actions on this PO through an authorized group."))
        if sup is not None and receivable and sup.get("supplier_status") != "Approved":
            affected = affected_materials is None or po.get("material_id") in affected_materials
            out.append(issue(
                "PO_RESTRICTED_SUPPLIER", Status.NEEDS_REVIEW if affected else Status.VALID, pid,
                f"Open PO from {sup.get('supplier_status')} supplier {sup['supplier_id']}"
                + (": sourcing actions on it are invalid and its receipts are excluded from simulation."
                   if affected else " (material not affected by this change)."),
                "Cancel or re-source this PO." if affected else "Handle outside this change."))
    return _result("purchase_orders", out)


def validate_all_inputs(data: dict, change_id: str | None = None) -> dict:
    """Run every validator for one engineering change. Issues on unrelated suppliers never block the change."""
    changes = to_records(data.get("engineering_changes"))
    change = next((c for c in changes if change_id is None or c.get("change_id") == change_id), None)
    results = {}
    if change is None:
        results["engineering_change"] = _result("engineering_change", [issue(
            "ECN_NOT_FOUND", Status.INSUFFICIENT_DATA, change_id or "<any>", "Engineering change not found.",
            "Load the engineering change record.")])
        affected = None
    else:
        results["engineering_change"] = validate_engineering_change(change, data.get("materials"))
        affected = {change.get("part_number"), change.get("new_material_id")} - {None}
    results["materials"] = validate_materials(data.get("materials"))
    results["inventory"] = validate_inventory(data.get("inventory"), data.get("materials"))
    results["bom"] = validate_bom(data.get("bom"), data.get("materials"))
    results["purchase_orders"] = validate_purchase_orders(data.get("purchase_orders"), data.get("suppliers"),
                                                           data.get("planning_groups"), affected)
    sup_result = validate_suppliers(data.get("suppliers"))
    cross = []
    if affected:
        pos = [p for p in to_records(data.get("purchase_orders")) if p.get("material_id") in affected]
        relevant = {p.get("supplier_id") for p in pos} | {
            g["supplier_id"] for g in to_records(data.get("planning_groups")) if g.get("material_id") in affected}
        for i in sup_result.issues:          # unrelated supplier issues become INFO
            if i.record not in relevant and i.status != Status.VALID:
                i.status, i.severity = Status.VALID, "INFO"
                i.description = f"(unrelated to {change.get('change_id')}) {i.description}"
        sup_result = _result("suppliers", sup_result.issues)
        stocked = {r.get("material_id") for r in to_records(data.get("inventory"))}
        for mid in sorted(affected - stocked):
            cross.append(issue("INV_MISSING_FOR_AFFECTED", Status.INSUFFICIENT_DATA, mid,
                               f"No inventory record for affected material {mid}.", "Load the stock record."))
        sups = {s["supplier_id"]: s for s in to_records(data.get("suppliers"))}
        approval = as_int(change.get("approval_week"))
        for p in pos:
            order = as_int(p.get("order_week"))
            if (approval is not None and order is not None and order >= approval
                    and p.get("material_id") == change.get("part_number")
                    and p.get("po_status") in RECEIVABLE_PO_STATUSES):
                cross.append(issue("PO_CREATED_AFTER_APPROVAL", Status.NEEDS_REVIEW, p["po_id"],
                                   f"Old-revision PO placed in W{order}, after the change was approved in W{approval} "
                                   "(purchasing block).", "Cancel this PO or get a documented exception."))
            s = sups.get(p.get("supplier_id"))
            if p.get("po_status") in RECEIVABLE_PO_STATUSES and s is not None and as_int(s.get("lead_time_weeks")) is None:
                cross.append(issue("SUP_LEAD_TIME_REQUIRED", Status.INSUFFICIENT_DATA, p["po_id"],
                                   f"Supplier {s['supplier_id']} on an affected PO has no lead time.",
                                   "Obtain the lead time before planning."))
    results["suppliers"] = sup_result
    results["cross_checks"] = _result("cross_checks", cross)
    status = worst_status(r.status for r in results.values())
    return {
        "change_id": change.get("change_id") if change else change_id,
        "status": status.value,
        "ready_for_simulation": status in (Status.VALID, Status.NEEDS_REVIEW),
        "results": {k: r.to_dict() for k, r in results.items()},
        "issues": [i.model_dump(mode="json") for r in results.values() for i in r.issues],
    }
