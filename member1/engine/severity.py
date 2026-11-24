"""Exception building and deterministic severity scoring.

score = 100 x (w_type x type_weight + w_impact x min(1, financial_impact / impact_cap) + w_urgency x urgency)
urgency = (H - week + 1) / H for an exception in week `week` of an H-week horizon (sooner = more urgent),
          1.0 for exceptions with no week (data problems block planning now).
Bands: score >= 75 CRITICAL, >= 50 HIGH, >= 25 MEDIUM, else LOW. All weights live in config/settings.yaml.
Blocking data problems (DATA_INVALID, DATA_INSUFFICIENT) never score below the blocking floor (80).
Ranking: score desc, then week asc, then exception_id - identical inputs give an identical order.
"""
from . import CONFIG

_S = CONFIG["severity"]

OWNERS = {
    "PRODUCTION_SHORTAGE": ("Production Planning", "Secure Rev C supply earlier (expedite / approved alternate) or adjust the effective week."),
    "REVISION_GAP": ("Engineering Change Board", "Align the Rev B use-up end with the Rev C effective week."),
    "REV_B_SCRAP_RISK": ("Materials Management", "Reduce, cancel or defer-and-cancel open Rev B POs; review use-up plan."),
    "REV_C_EXCESS": ("Purchasing", "Reduce or defer Rev C PO quantity to about four weeks of cover."),
    "SUPPLIER_RESTRICTION": ("Purchasing / Supplier Quality", "Do not source from this supplier; re-source the PO."),
    "LEAD_TIME_RISK": ("Purchasing", "Confirm the delivery date with the supplier; expedite only if offered."),
    "DATA_INSUFFICIENT": ("Master Data", "Supply the missing record before planning."),
    "DATA_INVALID": ("Master Data", "Correct the invalid record before planning."),
    "DATA_REVIEW": ("Production Planning", "Review and confirm the flagged record."),
}


def classify_severity(score: float) -> str:
    for level in ("CRITICAL", "HIGH", "MEDIUM"):
        if score >= _S["bands"][level]:
            return level
    return "LOW"


def calculate_severity_score(exception: dict, horizon_weeks: int) -> float:
    w = _S["weights"]
    impact = min(1.0, (exception.get("financial_impact") or 0) / _S["impact_cap"])
    week = exception.get("week")
    urgency = 1.0 if week is None else max(0.0, min(1.0, (horizon_weeks - week + 1) / horizon_weeks))
    score = 100 * (w["type"] * _S["type_weights"][exception["exception_type"]] + w["impact"] * impact + w["urgency"] * urgency)
    if exception["exception_type"] in _S["blocking_types"]:
        score = max(score, float(_S["blocking_floor"]))
    return round(score, 1)


def _issue_type(i: dict) -> str | None:
    code, status = i["code"], i["status"]
    if status == "VALID":
        return None
    if "NO_PERMITTED_REVISION" in code or code == "ECN_REVISION_GAP":
        return "REVISION_GAP"
    if "RESTRICTED_SUPPLIER" in code:
        return "SUPPLIER_RESTRICTION"
    if "LEAD_TIME" in code or "EXPEDITE" in code:
        return "LEAD_TIME_RISK" if status != "INSUFFICIENT_DATA" else "DATA_INSUFFICIENT"
    return {"INVALID": "DATA_INVALID", "INSUFFICIENT_DATA": "DATA_INSUFFICIENT"}.get(status, "DATA_REVIEW")


def rank_exceptions(exceptions: list[dict]) -> list[dict]:
    ranked = sorted(exceptions, key=lambda e: (-e["severity_score"], e["week"] if e["week"] is not None else 0, e["exception_id"]))
    for n, e in enumerate(ranked, start=1):
        e["severity_rank"] = n
    return ranked


def build_exceptions(simulation: dict) -> list[dict]:
    """Exceptions for one simulate_inventory() result, scored and ranked."""
    h = simulation.get("horizon_weeks") or CONFIG["horizon_weeks"]
    old, new = simulation.get("old_material_id"), simulation.get("new_material_id")
    raw = []

    def add(etype, material, week, qty, value, description, key=None):
        owner, action = OWNERS[etype]
        key = key or f"{material or 'NA'}-W{week if week is not None else 'NA'}"
        raw.append({"exception_id": f"EXC-{etype}-{key}",
                    "simulation_id": simulation.get("simulation_id"), "change_id": simulation.get("change_id"),
                    "exception_type": etype, "material_id": material, "week": week, "quantity": qty,
                    "financial_impact": float(value), "description": description, "recommended_action": action,
                    "owner_role": owner, "status": "OPEN"})

    for w in simulation.get("weeks", []):
        if w["shortage"] > 0:
            mat = new if w["applicable_revision"] == "C" else old
            add("PRODUCTION_SHORTAGE", mat, w["week"], w["shortage"], w["shortage"] * CONFIG["shortage_cost_per_unit"],
                f"W{w['week']}: {w['shortage']} of {w['demand']} brackets cannot be supplied.")
    ex = simulation.get("excess") or {}
    if ex.get("rev_b_scrap_units"):
        add("REV_B_SCRAP_RISK", old, simulation.get("use_up_end_week"), ex["rev_b_scrap_units"], ex["rev_b_scrap_value"],
            f"{ex['rev_b_scrap_units']} Rev B units unusable after use-up end W{simulation.get('use_up_end_week')} "
            f"(incl. {ex.get('rev_b_scrap_from_safety_stock', 0)} former safety stock, "
            f"{ex.get('rev_b_post_use_up_receipts', 0)} received after use-up end).")
    if ex.get("rev_c_excess_value"):
        cover = CONFIG["coverage_weeks"] * ex["average_weekly_demand"]
        add("REV_C_EXCESS", new, h, round(ex["rev_c_closing_units"] - cover), ex["rev_c_excess_value"],
            f"Rev C closing stock {ex['rev_c_closing_units']} exceeds {CONFIG['coverage_weeks']} weeks of cover ({cover:g}).")
    for i in simulation.get("issues", []):
        etype = _issue_type(i)
        if etype:
            add(etype, None, i.get("week"), None, 0, f"{i['code']} on {i['record']}: {i['description']}",
                key=f"{i['code']}-{i['record']}")
    seen, unique = set(), []
    for e in raw:                       # the same issue reported twice keeps its first occurrence
        if e["exception_id"] not in seen:
            seen.add(e["exception_id"])
            e["severity_score"] = calculate_severity_score(e, h)
            e["severity_level"] = classify_severity(e["severity_score"])
            unique.append(e)
    return rank_exceptions(unique)
