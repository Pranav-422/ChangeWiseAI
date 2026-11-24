import json
import sys
import types

import pytest
from jsonschema import Draft202012Validator

from member3.services.member1_adapter import Member1Adapter, Member1ContractError
from member3.settings import ROOT


def test_production_module_is_member1s():
    from member3.settings import load_settings
    assert load_settings()["member1"]["module"] == "member3.integration.member1_module"


def test_stand_in_is_declared_synthetic(member1):
    assert member1.synthetic and "standin" in member1.name


def test_incomplete_member1_module_is_refused(monkeypatch):
    module = types.ModuleType("half_member1")
    module.list_scenarios = list
    monkeypatch.setitem(sys.modules, "half_member1", module)
    with pytest.raises(Member1ContractError, match="load_dataset"):
        Member1Adapter("half_member1")


def test_bom_paths_reach_every_assembly(member1):
    impact = member1.bom_impact("BRK-B")
    assert impact["finished_assemblies"] == ["PUMP-ASSY", "SPARE-KIT"]
    assert ["BRK-B", "MOUNT-SUB", "PUMP-ASSY"] in impact["paths"]
    assert member1.bom_impact("UNUSED")["impact_status"] == "NOT_USED"


def test_bad_bom_output_is_refused(member1, monkeypatch):
    monkeypatch.setattr(member1._module, "bom_impact", lambda m: {"paths": []})
    with pytest.raises(Member1ContractError):
        member1.bom_impact("BRK-B")


def test_severity_order_matches_the_formula(member1):
    data = member1.load_dataset("REV_C_DELAY")
    found = member1.exceptions(data, member1.baseline(data))
    assert [e["severity"] for e in found] == sorted((e["severity"] for e in found), reverse=True)
    first = next(e for e in found if e["type"] == "SHORTAGE" and e["week"] == 6)
    assert first["severity"] == 100 * 400 * 3 / (5 + 1)


def test_broken_records_are_not_simulated(member1):
    data = member1.load_dataset("MISSING_RECORD")
    assert member1.baseline(data) is None and member1.exceptions(data, None) == []


def test_member2_output_follows_its_contract(member1, member2):
    schema = json.loads((ROOT / "member2/contracts/output_schema.json").read_text(encoding="utf-8"))
    for scenario in member1.list_scenarios():
        Draft202012Validator(schema).validate(member2.optimize(member1.load_dataset(scenario)))


def test_member2_evaluation_of_a_custom_plan(member1, member2):
    data = member1.load_dataset("BASE")
    good = member2.evaluate([{"action": "REDUCE_REV_B_PO", "po_id": "PO-001", "quantity": 50}], data)
    assert good["feasibility"] == "FEASIBLE" and good["robustness"]["denominator"] == 9 and len(good["weekly"]) == 10
    bad = member2.evaluate([{"action": "REDUCE_REV_B_PO", "po_id": "PO-001", "quantity": 70}], data)
    assert bad["feasibility"] == "REJECTED" and bad["rejection_reasons"]


def test_menu_options_are_all_feasible(member1, member2):
    data = member1.load_dataset("BASE")
    for options in member2.menus(data).values():
        for option in options:
            assert member2.evaluate(option, data)["feasibility"] == "FEASIBLE"
