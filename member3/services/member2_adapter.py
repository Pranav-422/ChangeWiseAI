"""The only door to Member 2's engine. Every ranking, cost and rule check comes from here."""
import json
from copy import deepcopy

from member2.engine.action_generator import build_menus
from member2.engine.config import load_config
from member2.engine.constraints import action_violations, input_errors
from member2.engine.pipeline import evaluate_custom_plan, run_optimization, snapshot_hash
from member2.engine.recommendation import describe_plan
from member2.engine.robustness import apply_shock, compare_plan_robustness
from member2.evaluation.comparison import compare_configurations


def plain(value):
    """The JSON form, which is what is stored and what replay compares."""
    return json.loads(json.dumps(value))


class Member2Adapter:
    def __init__(self, simulate, config=None):
        self.simulate = simulate
        self.config = config or load_config()

    def config_for_week(self, week):
        config = deepcopy(self.config)
        config["action_space"]["effective_weeks"] = [week]
        return config

    def optimize(self, dataset, config=None):
        return plain(run_optimization(dataset, config or self.config, self.simulate))

    def evaluate(self, actions, dataset):
        """A planner-chosen plan under the same rules, plus the fields a recommendation carries."""
        record = evaluate_custom_plan(actions, dataset, self.config, self.simulate)
        if record["feasibility"] == "FEASIBLE":
            record["robustness"] = compare_plan_robustness(
                [record], dataset, self.simulate, self.config)[record["plan_id"]]
            record["weekly"] = record["simulation"]["weekly"]
        record.pop("simulation", None)
        return plain({**record, "summary": describe_plan(record)})

    def menus(self, dataset):
        """Eligible options per decision, for the planner's modify form."""
        menus = build_menus(dataset, self.config)
        return {"Changeover": menus["changeovers"], **menus["po_menus"]}

    def compare(self, dataset, result):
        return compare_configurations(dataset, self.config, self.simulate, result)

    def same_result(self, stored_result, dataset, config):
        again = self.optimize(dataset, config)
        return {**again, "computation_seconds": 0} == {**stored_result, "computation_seconds": 0}

    @staticmethod
    def action_problems(action, dataset):
        return action_violations(action, dataset)

    @staticmethod
    def input_problems(dataset):
        return input_errors(dataset)

    @staticmethod
    def hash(dataset):
        return snapshot_hash(dataset)

    @staticmethod
    def shock(dataset, lead_time_delta, demand_change_percent):
        """Member 2's own stress rules on an already isolated copy."""
        return apply_shock(dataset, {"lead_time_shock": lead_time_delta,
                                     "demand_shock": demand_change_percent / 100})
