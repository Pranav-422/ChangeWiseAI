"""The only door to Member 1. Swap the module in config/settings.yaml.

Contract: list_scenarios(), load_dataset(id), validate_ecn(fields, dataset) -> [{code, field, message}],
bom_impact(material_id), simulate_inventory(**kwargs), score_exceptions(dataset, simulation).
"""
from importlib import import_module

from member2.engine.constraints import input_errors

from ..settings import load_settings

_FUNCTIONS = ("list_scenarios", "load_dataset", "validate_ecn", "bom_impact", "simulate_inventory",
              "score_exceptions")
_BOM_KEYS = {"material_id", "direct_parents", "indirect_parents", "finished_assemblies", "paths", "impact_status"}
_EXCEPTION_KEYS = {"exception_id", "type", "week", "units", "impact_rs", "severity", "band", "description"}


class Member1ContractError(RuntimeError):
    pass


class Member1Adapter:
    def __init__(self, module_name=None):
        self.name = module_name or load_settings()["member1"]["module"]
        self._module = import_module(self.name)
        missing = [f for f in _FUNCTIONS if not callable(getattr(self._module, f, None))]
        if missing:
            raise Member1ContractError(f"{self.name} lacks {', '.join(missing)}")

    @property
    def synthetic(self):
        return bool(getattr(self._module, "SYNTHETIC", False))

    @property
    def simulate(self):
        return self._module.simulate_inventory

    def list_scenarios(self):
        return self._module.list_scenarios()

    def load_dataset(self, scenario_id):
        return self._module.load_dataset(scenario_id)

    def validate_ecn(self, fields, dataset):
        return self._module.validate_ecn(fields, dataset)

    def baseline(self, dataset):
        """No-action simulation, or None when the records are too broken to simulate."""
        if input_errors(dataset):
            return None
        change = {**dataset["engineering_change"], "consumption_policy": "CUTOVER"}
        return self.simulate(materials=dataset["materials"], inventory=dataset["inventory"],
                             demand=dataset["demand"], purchase_orders=dataset["purchase_orders"],
                             engineering_change=change)

    def bom_impact(self, material_id):
        impact = self._module.bom_impact(material_id)
        if not _BOM_KEYS <= set(impact):
            raise Member1ContractError(f"bom_impact lacks {', '.join(sorted(_BOM_KEYS - set(impact)))}")
        return impact

    def exceptions(self, dataset, simulation):
        if simulation is None:
            return []
        found = self._module.score_exceptions(dataset, simulation)
        for item in found:
            if not _EXCEPTION_KEYS <= set(item):
                raise Member1ContractError(f"exception lacks {', '.join(sorted(_EXCEPTION_KEYS - set(item)))}")
        return found
