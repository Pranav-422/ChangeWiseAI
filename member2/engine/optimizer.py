"""Official objective: lexicographic minimum of (S, E + C). Two levels, never a weighted sum."""
from functools import cmp_to_key


def calculate_secondary_cost(excess_value, action_cost):
    return round(excess_value + action_cost, 2)


def objective(plan):
    return plan["shortage_units"], round(plan["secondary_cost"], 2)


def _tie_key(plan):
    """Identical objectives: fewest actions, then plan ID. Never decides between different objectives."""
    return len(plan["actions"]), plan["plan_id"]


def compare_plans(plan_a, plan_b):
    """-1 when plan_a ranks first, 1 when plan_b does, 0 for the same plan."""
    for key in (objective, _tie_key):
        a, b = key(plan_a), key(plan_b)
        if a != b:
            return -1 if a < b else 1
    return 0


def rank_feasible_plans(plans):
    """Rank feasible plans. Returns new records with a 1-based `rank`; rejected plans are excluded."""
    feasible = [p for p in plans if p.get("feasibility", "FEASIBLE") == "FEASIBLE"]
    ordered = sorted(feasible, key=cmp_to_key(compare_plans))
    return [{**plan, "rank": rank} for rank, plan in enumerate(ordered, 1)]


def mark_redundant(ranked):
    """Flag plans that add actions to another plan without changing either objective.

    Deferring an order that nobody is waiting for is free, so every good plan has look-alikes with
    such an action bolted on. They stay in the ranked list with `redundant_of` filled in.
    """
    groups = {}
    for plan in ranked:
        groups.setdefault(objective(plan), []).append(
            (plan["plan_id"], {repr(sorted(a.items())) for a in plan["actions"]}))
    marked = []
    for plan in ranked:
        mine = {repr(sorted(a.items())) for a in plan["actions"]}
        parent = next((pid for pid, acts in groups[objective(plan)] if acts < mine), None)
        marked.append({**plan, "redundant_of": parent})
    return marked


def select_top_plans(plans, limit=3):
    """First `limit` ranked plans, skipping look-alikes flagged by mark_redundant."""
    return [p for p in plans if not p.get("redundant_of")][:limit]
