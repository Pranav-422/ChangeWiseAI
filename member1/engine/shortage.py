"""Production shortage: S = sum over weeks of unmet demand.

Unmet demand is computed once per week for the bracket position (Rev B and Rev C together), so the same
demand is never counted twice during the changeover. Demand and usage are reported separately.
"""
from . import CONFIG


def calculate_weekly_unmet_demand(weeks: list[dict]) -> list[dict]:
    return [{"week": w["week"], "unmet_demand": int(w["shortage"])} for w in weeks]


def calculate_shortage_summary(weeks: list[dict], material_by_revision: dict | None = None,
                               cost_per_unit: float | None = None) -> dict:
    """`weeks` rows need "week" and "shortage"; "applicable_revision" ("B"/"C"/None) names the affected material."""
    weekly = calculate_weekly_unmet_demand(weeks)
    short = [w for w in weekly if w["unmet_demand"] > 0]
    total = sum(w["unmet_demand"] for w in weekly)
    cost = CONFIG["shortage_cost_per_unit"] if cost_per_unit is None else cost_per_unit
    by_rev = material_by_revision or {}
    affected = sorted({by_rev.get(w.get("applicable_revision") or "B", w.get("applicable_revision") or "B")
                       for w in weeks if w["shortage"] > 0})
    return {
        "weekly_unmet_demand": weekly,
        "total_shortage_units": total,
        "first_shortage_week": short[0]["week"] if short else None,
        "shortage_weeks": len(short),
        "shortage_week_list": [w["week"] for w in short],
        "affected_materials": affected,
        "estimated_financial_impact": total * cost,
        "cost_per_unit_basis": cost,
    }
