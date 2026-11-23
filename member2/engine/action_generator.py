"""Candidate action space: complete, duplicate-free, deterministic combinations of actions.

A menu is a list of options and an option is a list of actions (the empty list means "leave it
alone"). A plan picks one option from the changeover menu and one from every purchase order's menu.
"""
import hashlib
import json
from itertools import product
from math import prod

from .config import load_config
from .constraints import (
    EDITABLE_PO, action_violations, check_contradictions, po_arrival_reasons, po_supplier_reasons,
)


def canonical_actions(actions):
    return sorted(actions, key=lambda a: json.dumps(a, sort_keys=True))


def make_plan(actions, data, source="ENUMERATION"):
    """Build a plan record. The ID is a hash of the actions, so equal plans get equal IDs."""
    actions = canonical_actions(actions)
    digest = hashlib.sha256(json.dumps(actions, sort_keys=True).encode()).hexdigest()
    shift = next((a for a in actions if a["action"] == "SHIFT_EFFECTIVE_WEEK"), None)
    run_out = any(a["action"] == "CONTINUE_REV_B" for a in actions)
    return {
        "plan_id": f"PLAN-{digest[:10]}",
        "effective_week": shift["to_week"] if shift else data["engineering_change"]["effective_week"],
        "consumption_policy": "RUN_OUT" if run_out else "CUTOVER",
        "actions": actions,
        "source": source,
    }


def _screen(candidates, data):
    """Split candidate actions into eligible ones and skipped ones with reasons."""
    eligible, skipped = [], []
    for action in candidates:
        reasons = action_violations(action, data)
        if reasons:
            skipped.append({"action": action, "reasons": reasons})
        else:
            eligible.append(action)
    return eligible, skipped


def generate_effective_week_actions(data, config):
    """Changeover menu: original week, shifted weeks, or running Rev B out until its use-up end."""
    change = data["engineering_change"]
    original, use_up = change["effective_week"], change["use_up_end_week"]
    candidates = [{"action": "SHIFT_EFFECTIVE_WEEK", "from_week": original, "to_week": week}
                  for week in config["action_space"]["effective_weeks"] if week != original]
    candidates += [{"action": "CONTINUE_REV_B", "through_week": week} for week in (use_up, use_up + 1)]
    eligible, skipped = _screen(candidates, data)
    return [[]] + [[action] for action in eligible], skipped


def generate_po_actions(data, config):
    """Per-order options for reduce, cancel, defer and expedite, before supplier changes."""
    limits, change = config["action_space"], data["engineering_change"]
    menus, skipped = {}, []
    for po in data["purchase_orders"]:
        po_id = po["po_id"]
        if po["status"] in ("CANCELLED", "RECEIVED"):
            continue
        base = {"po_id": po_id}
        if po["material_id"] == change["old_material_id"]:
            lot = po["reduction_lot"] or po["max_reduction_qty"]
            most = min(po["max_reduction_qty"], po["quantity"])
            reductions = [{"action": "REDUCE_REV_B_PO", **base, "quantity": q}
                          for q in range(lot, most + 1, lot)] if lot else []
            timings = [{"action": "DEFER_REV_B_PO", **base, "weeks": w}
                       for w in range(1, limits["max_deferral_weeks"] + 1)]
            cancels = [{"action": "CANCEL_REV_B_PO", **base}]
        elif po["material_id"] == change["new_material_id"]:
            reductions, cancels = [], []
            timings = [{"action": "EXPEDITE_REV_C_PO", **base, "weeks": w}
                       for w in range(1, limits["max_expedite_weeks"] + 1)]
            timings += [{"action": "DEFER_REV_C_PO", **base, "weeks": w}
                        for w in range(1, limits["max_deferral_weeks"] + 1)]
        else:
            continue
        keep_reasons = po_supplier_reasons(po, data)
        if keep_reasons:
            skipped.append({"action": {"action": "KEEP_PO", **base}, "reasons": keep_reasons})
            reductions, timings, options = [], [], []
        else:
            reductions, skip_r = _screen(reductions, data)
            timings, skip_t = _screen(timings, data)
            skipped += skip_r + skip_t
            options = [[a for a in pair if a]
                       for pair in product([None] + reductions, [None] + timings)]
        cancels, skip_c = _screen(cancels, data)
        skipped += skip_c
        menus[po_id] = options + [[action] for action in cancels]
    return menus, skipped


def generate_supplier_actions(data, config):
    """Alternate sources for every editable Rev C order."""
    candidates = [
        {"action": "ALTERNATE_SUPPLIER", "po_id": po["po_id"], "supplier_id": s["supplier_id"]}
        for po in data["purchase_orders"]
        if po["material_id"] == data["engineering_change"]["new_material_id"]
        and po["status"] in EDITABLE_PO
        for s in data["suppliers"] if s["supplier_id"] != po["supplier_id"]
        and any(m["supplier_id"] == s["supplier_id"] and m["material_id"] == po["material_id"]
                for m in data["supplier_materials"])
    ]
    return _screen(candidates, data)


def po_arrival_option(po, option, data):
    """Lead-time reasons that make this menu option infeasible on its own."""
    names = {a["action"] for a in option}
    if names & {"EXPEDITE_REV_C_PO", "ALTERNATE_SUPPLIER", "CANCEL_REV_B_PO"}:
        return []
    shift = sum(a["weeks"] for a in option if a["action"].startswith("DEFER"))
    return po_arrival_reasons({**po, "arrival_week": po["arrival_week"] + shift}, data)


def build_menus(data, config):
    """Everything both the enumerator and the solvers choose from."""
    changeovers, skipped = generate_effective_week_actions(data, config)
    po_menus, skip_po = generate_po_actions(data, config)
    alternates, skip_alt = generate_supplier_actions(data, config)
    for action in alternates:
        po_menus[action["po_id"]].append([action])
    for po in data["purchase_orders"]:  # an order whose own date is infeasible cannot be left alone
        po_id = po["po_id"]
        menu = po_menus.get(po_id, [])
        plain = [o for o in menu if po_arrival_option(po, o, data)]
        if plain:
            po_menus[po_id] = [o for o in menu if o not in plain]
            skipped.append({"action": {"action": "KEEP_PO", "po_id": po_id},
                            "reasons": po_arrival_option(po, plain[0], data)})
    return {"changeovers": changeovers, "po_menus": po_menus,
            "skipped": skipped + skip_po + skip_alt}


def combination_count(menus):
    return len(menus["changeovers"]) * prod(len(o) for o in menus["po_menus"].values())


def combine_actions(menus):
    """Yield the flat action list of every complete combination, in a fixed order."""
    for picks in product(menus["changeovers"], *menus["po_menus"].values()):
        yield [action for option in picks for action in option]


def validate_action_combinations(plans):
    """Drop duplicates and contradictory plans. Returns (kept plans, dropped records)."""
    kept, dropped, seen = [], [], set()
    for plan in plans:
        if plan["plan_id"] in seen:
            dropped.append({"plan_id": plan["plan_id"], "reason": "DUPLICATE"})
            continue
        seen.add(plan["plan_id"])
        reasons = check_contradictions(plan)
        if reasons:
            dropped.append({"plan_id": plan["plan_id"], "reason": reasons})
        else:
            kept.append(plan)
    return kept, dropped


def _probe_actions(data):
    """Rules no eligible action can touch: a new Rev B order after approval."""
    po = next((p for p in data["purchase_orders"]
               if p["material_id"] == data["engineering_change"]["old_material_id"]), None)
    if po is None:
        return []
    return [{"action": "CREATE_REV_B_PO", "supplier_id": po["supplier_id"],
             "purchasing_group": po["purchasing_group"], "quantity": po["quantity"]}]


def generate_candidate_plans(data, config=None):
    """Complete candidate set. `truncated` is True when the space exceeds max_candidates."""
    config = config or load_config()
    menus = build_menus(data, config)
    _, skipped_new = _screen(_probe_actions(data), data)
    skipped = menus["skipped"] + skipped_new
    count = combination_count(menus)
    truncated = count > config["action_space"]["max_candidates"]
    plans = [] if truncated else [make_plan(a, data) for a in combine_actions(menus)]
    if config["action_space"]["include_probe_plans"]:
        plans += [make_plan([] if s["action"]["action"] == "KEEP_PO" else [s["action"]], data, "PROBE")
                  for s in skipped]
    plans, dropped = validate_action_combinations(plans)
    return {"plans": plans, "menus": menus, "skipped_actions": skipped, "dropped_plans": dropped,
            "combination_count": count, "truncated": truncated}
