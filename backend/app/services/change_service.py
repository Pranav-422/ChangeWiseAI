"""Engineering changes: overview, BOM impact, inventory simulation and exceptions. Every number is Member 1's."""
import json

from member1.engine.bom_impact import generate_bom_impact_report
from member1.engine.data_loader import as_int, as_num, to_records
from member1.engine.inventory import simulate_from_data
from member1.engine.scenarios import SCENARIOS
from member1.engine.validation import validate_all_inputs
from member3.application.access_control import NotAllowed
from member3.database.repositories import records
from member3.services import approval_service, audit_service, planning_service

from ..core.database import acting, read, transaction
from ..core.errors import ApiError, not_found
from ..integrations import member1_postgres as source
from ..security import permissions
from . import action_service, audit_queries, planning

# Member 1 names business teams; these roles of the application work on their exceptions. The planner may always.
_EXCEPTION_OWNERS = {"Purchasing": ("Purchasing",), "Purchasing / Supplier Quality": ("Purchasing", "Quality"),
                     "Engineering Change Board": ("Engineering",), "Master Data": ("Engineering",),
                     "Materials Management": ("Purchasing",), "Production Planning": ()}
_STATUS_ORDER = {"OPEN": ("ACKNOWLEDGED", "RESOLVED"), "ACKNOWLEDGED": ("RESOLVED",), "RESOLVED": ()}


def scenario_key(change_id, scenario):
    """Identifies a dataset for the adapters."""
    key = source.key_of(change_id, scenario)
    if key not in source.list_scenarios():
        raise not_found(f"Scenario {scenario} of {change_id}")
    return key


def _change(tables, change_id):
    found = next((c for c in to_records(tables["engineering_changes"]) if c["change_id"] == change_id), None)
    if found is None:
        raise not_found(f"Engineering change {change_id}")
    return {**found, "interchangeability": bool(found["interchangeability"])}


def _scenarios(change_id, keys):
    return [{"scenario_id": s, "description": text} for s, text in SCENARIOS.items()
            if source.key_of(change_id, s) in keys]


def _workflow(key):
    """Latest review, run and decision, without their large JSON columns."""
    with read() as db:
        review = db.execute("SELECT review_id, status, validation->>'validation_status' AS validation_status, created_at "
                            "FROM ecn_reviews WHERE scenario_id = ? ORDER BY rowid DESC LIMIT 1", [key]).fetchone()
        run = db.execute("SELECT r.run_id, r.decision, r.created_at, a.decision AS approval, a.closed_at "
                         "FROM planning_runs r LEFT JOIN approvals a USING (run_id) WHERE r.scenario_id = ? "
                         "ORDER BY r.rowid DESC LIMIT 1", [key]).fetchone()
    return {"latest_review": review, "latest_run": run, "stage": planning_service.change_stage(key)}


def list_changes():
    tables, keys = source.load_tables(), source.list_scenarios()
    return [{**_change(tables, c["change_id"]), "scenarios": _scenarios(c["change_id"], keys),
             "validation_status": validate_all_inputs(tables, c["change_id"])["status"],
             **_workflow(source.key_of(c["change_id"], "base"))}
            for c in to_records(tables["engineering_changes"])]


def _simulate(change_id, scenario):
    tables = source.scenario_tables(scenario_key(change_id, scenario))
    return tables, simulate_from_data(tables, change_id, scenario_id=scenario.upper())


def _store(db, result):
    """Member 1's save_simulation_run() in PostgreSQL. Identical inputs map to the same row."""
    excess = result["excess"] or {}
    db.execute("INSERT INTO core.simulation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
               [result["simulation_id"], result["change_id"], result["scenario_id"], result["input_snapshot_hash"],
                result["engine_version"], records.now(), result["validation_status"], result["total_shortage_units"],
                result["excess_value"], excess.get("rev_b_scrap_units"), excess.get("rev_c_closing_units"),
                json.dumps(result, sort_keys=True)])
    db.executemany(
        "INSERT INTO core.exceptions (simulation_id, exception_id, change_id, exception_type, material_id, week, quantity, "
        "financial_impact, severity_score, severity_level, severity_rank, description, recommended_action, owner_role, "
        "status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
        [(result["simulation_id"], e["exception_id"], result["change_id"], e["exception_type"], e["material_id"],
          e["week"], e["quantity"], e["financial_impact"], e["severity_score"], e["severity_level"],
          e["severity_rank"], e["description"], e["recommended_action"], e["owner_role"], e["status"])
         for e in result["exceptions"]])


def simulate(change_id, scenario, user):
    permissions.require(user, "RUN_SIMULATION")
    tables, result = _simulate(change_id, scenario)
    with acting(user.user_id), transaction() as db:
        _store(db, result)
        audit_service.append(db, "SIMULATION_RUN", result["simulation_id"], user, {
            "change_id": change_id, "scenario": scenario, "status": result["validation_status"],
            "input_hash": result["input_snapshot_hash"], "engine_version": result["engine_version"],
            "shortage": result["total_shortage_units"], "excess_value": result["excess_value"]})
    return _inventory(tables, result, change_id, scenario)


def inventory(change_id, scenario):
    return _inventory(*_simulate(change_id, scenario), change_id, scenario)


def _inventory(tables, result, change_id, scenario):
    pair = (result["old_material_id"], result["new_material_id"])
    with read() as db:
        stored = db.execute("SELECT simulation_timestamp AS at FROM core.simulation_runs WHERE simulation_id = ?",
                            [result["simulation_id"]]).fetchone()
    suppliers = {s["supplier_id"]: s for s in to_records(tables["suppliers"])}
    orders = [{"po_id": p["po_id"], "material_id": p["material_id"], "supplier_id": p["supplier_id"],
               "supplier_name": suppliers.get(p["supplier_id"], {}).get("supplier_name"),
               "supplier_status": suppliers.get(p["supplier_id"], {}).get("supplier_status"),
               "quantity": as_int(p["quantity"]), "order_week": as_int(p["order_week"]),
               "arrival_week": as_int(p["arrival_week"]), "status": p["po_status"],
               "change_deadline_week": as_int(p["cancel_allowed_until"])}
              for p in to_records(tables["purchase_orders"]) if p["material_id"] in pair]
    stock = [{"material_id": i["material_id"], "on_hand": as_int(i["on_hand"]), "reserved": as_int(i["reserved"]),
              "safety_stock": as_int(i["safety_stock"]), "inventory_date": i["inventory_date"]}
             for i in to_records(tables["inventory"]) if i["material_id"] in pair]
    materials = {m["material_id"]: m for m in to_records(tables["materials"])}
    return {"change_id": change_id, "scenario_id": scenario, "simulation_id": result["simulation_id"],
            "input_hash": result["input_snapshot_hash"], "engine_version": result["engine_version"],
            "status": result["validation_status"], "effective_week": result["effective_week"],
            "use_up_end_week": result["use_up_end_week"], "horizon_weeks": result["horizon_weeks"],
            "stored_at": stored and stored["at"], "weeks": result["weeks"],
            "total_shortage_units": result["total_shortage_units"], "excess_value": result["excess_value"],
            "excess": result["excess"], "shortage": result["shortage"], "issues": result["issues"],
            "materials": [{"material_id": m, "revision": materials[m]["revision"], "name": materials[m]["material_name"],
                           "unit_cost": as_num(materials[m]["unit_cost"])} for m in pair if m in materials],
            "stock": stock, "purchase_orders": orders,
            "material_balance": _balance(result)}


def _balance(result):
    """Where the old revision's supply goes. Sums of Member 1's weekly rows, so no rule is applied here."""
    weeks, excess = result["weeks"], result["excess"]
    if not weeks or not excess:
        return None
    return {"opening": weeks[0]["rev_b_opening"], "receipts": sum(w["rev_b_receipts"] for w in weeks),
            "used": sum(w["rev_b_usage"] for w in weeks), "reserved": excess["rev_b_reserved_excluded"],
            "scrap": excess["rev_b_scrap_units"]}


def exceptions(change_id, scenario):
    return _exceptions(_simulate(change_id, scenario)[1], change_id, scenario)


def _exceptions(result, change_id, scenario):
    """Member 1's ranked exceptions, with the status people gave them for exactly these inputs."""
    with read() as db:
        states = {r["exception_id"]: r for r in db.execute(
            "SELECT exception_id, status, updated_at FROM core.exceptions WHERE simulation_id = ?", [result["simulation_id"]])}
    items = []
    for e in result["exceptions"]:
        state = states.get(e["exception_id"])
        items.append({**{k: e[k] for k in (
            "exception_id", "simulation_id", "change_id", "exception_type", "material_id", "week", "quantity",
            "financial_impact", "severity_score", "severity_level", "severity_rank", "description",
            "recommended_action", "owner_role")},
            "status": state["status"] if state else e["status"], "updated_at": state and state["updated_at"],
            "allowed_statuses": list(_STATUS_ORDER[state["status"] if state else e["status"]]),
            "owner_roles": ["Planner", *_EXCEPTION_OWNERS.get(e["owner_role"], ())]})
    return {"change_id": change_id, "scenario_id": scenario, "simulation_id": result["simulation_id"], "items": items}


def update_exception(change_id, scenario, exception_id, status, user):
    permissions.require(user, "UPDATE_EXCEPTION")
    _, result = _simulate(change_id, scenario)
    item = next((e for e in result["exceptions"] if e["exception_id"] == exception_id), None)
    if item is None:
        raise not_found(f"Exception {exception_id}")
    if user.role != "Planner" and user.role not in _EXCEPTION_OWNERS.get(item["owner_role"], ()):
        raise NotAllowed(f"{user.role} does not own this exception.")
    with acting(user.user_id), transaction() as db:
        _store(db, result)
        key = [result["simulation_id"], exception_id]
        before = db.execute("SELECT status FROM core.exceptions WHERE simulation_id = ? AND exception_id = ?", key).fetchone()["status"]
        if status not in _STATUS_ORDER[before]:
            raise ApiError(409, "INVALID_TRANSITION", f"An exception that is {before.lower()} cannot become {status.lower()}.")
        db.execute("UPDATE core.exceptions SET status = ?, updated_at = now() WHERE simulation_id = ? AND exception_id = ?",
                   [status, *key])
        audit_service.append(db, "EXCEPTION_STATUS", exception_id, user, {
            "simulation_id": result["simulation_id"], "from": before, "to": status})
    return next(e for e in exceptions(change_id, scenario)["items"] if e["exception_id"] == exception_id)


def bom_impact(change_id, scenario):
    tables = source.scenario_tables(scenario_key(change_id, scenario))
    return _bom(tables, _change(tables, change_id))


def _bom(tables, change):
    materials = {m["material_id"]: m for m in to_records(tables["materials"])}
    reports = {m: generate_bom_impact_report(m, tables["bom"], tables["materials"], change)
               for m in (change["part_number"], change["new_material_id"])}
    on_path = {m for r in reports.values() for a in r["affected_assemblies"] for m in a["path_ids"]} | set(reports)
    edges = [{"parent": b["parent_material_id"], "child": b["child_material_id"],
              "quantity": as_num(b["quantity_per_parent"]), "effective_from": as_int(b["effective_from"]),
              "effective_to": as_int(b["effective_to"])}
             for b in to_records(tables["bom"]) if {b["parent_material_id"], b["child_material_id"]} <= on_path]
    old = reports[change["part_number"]]
    return {"change_id": change["change_id"], "old_material_id": change["part_number"], "new_material_id": change["new_material_id"],
            "impact_status": old["impact_status"], "direct_parents": old["direct_parents"],
            "indirect_parents": old["indirect_parents"], "finished_products": old["affected_finished_products"],
            "cycles": old["cycles"],
            "nodes": [{"material_id": m, "name": materials[m]["material_name"], "type": materials[m]["material_type"],
                       "revision": materials[m]["revision"], "status": materials[m]["material_status"],
                       "description": materials[m]["description"]} for m in sorted(on_path) if m in materials],
            "edges": edges,
            "paths": [{"material_id": m, "assembly": a["assembly"], "assembly_type": a["assembly_type"],
                       "path_ids": a["path_ids"], "quantity": a["quantity_per_assembly"]}
                      for m, r in reports.items() for a in r["affected_assemblies"]]}


def overview(change_id, scenario, user):
    """Everything the executive dashboard and the change workspace open with."""
    key = scenario_key(change_id, scenario)
    tables, result = _simulate(change_id, scenario)
    change = _change(tables, change_id)
    state = _workflow(key)
    run = planning.summary(state["latest_run"]["run_id"]) if state["latest_run"] else None
    found = validate_all_inputs(tables, change_id)
    can_audit = "VIEW_AUDIT" in permissions.granted(user.role)
    return {"change": change, "scenario_id": scenario, "scenarios": _scenarios(change_id, source.list_scenarios()),
            "validation": {"status": found["status"], "issues": [
                {k: i[k] for k in ("code", "status", "record", "description", "resolution")} for i in found["issues"]
                if i["status"] != "VALID"]},
            "stage": state["stage"], "latest_review": state["latest_review"], "run": run,
            "inventory": _inventory(tables, result, change_id, scenario),
            "exceptions": _exceptions(result, change_id, scenario)["items"],
            "finished_products": _bom(tables, change)["finished_products"],
            "pending_approvals": len(approval_service.pending_runs()),
            "actions": action_service.list_items(run["run_id"]) if run else [],
            "recent_events": audit_queries.page(limit=6, offset=0)["items"] if can_audit else []}
