"""Excess inventory value: E = E_B + E_C.

E_B = RevB_leftover x UnitCost_B
E_C = max(0, RevC_closing - coverage_weeks x D) x UnitCost_C      (coverage_weeks = 4 in settings.yaml)

The simulator decides what goes in: RevB_leftover is free Rev B stock (on hand minus reserved) at the use-up end,
plus Rev B receipts scheduled after the use-up end (they can never be consumed). Reserved stock is excluded:
it belongs to its reservation (service kits). Former safety stock is included but reported separately.
"""
from . import CONFIG


def _non_negative(**values):
    for k, v in values.items():
        if v is None or v < 0:
            raise ValueError(f"{k} must be >= 0, got {v!r}")


def calculate_rev_b_scrap_value(leftover_units, unit_cost) -> float:
    _non_negative(leftover_units=leftover_units, unit_cost=unit_cost)
    return float(leftover_units * unit_cost)


def calculate_rev_c_excess_value(closing_stock, average_weekly_demand, unit_cost, coverage_weeks=None) -> float:
    weeks = CONFIG["coverage_weeks"] if coverage_weeks is None else coverage_weeks
    _non_negative(closing_stock=closing_stock, average_weekly_demand=average_weekly_demand,
                  unit_cost=unit_cost, coverage_weeks=weeks)
    return float(max(0.0, closing_stock - weeks * average_weekly_demand) * unit_cost)


def calculate_total_excess(rev_b_value, rev_c_value) -> float:
    _non_negative(rev_b_value=rev_b_value, rev_c_value=rev_c_value)
    return float(rev_b_value + rev_c_value)
