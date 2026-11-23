"""Money. Fees come from the original input records, never from the modified copy."""
from .constraints import po_of

COVERAGE_WEEKS = 4


def calculate_action_cost(actions, data):
    """C = expedite fees + cancellation fees + reduction fees (per-action breakdown kept)."""
    fees = {"expedite": 0, "cancellation": 0, "reduction": 0}
    for action in actions:
        po, name = po_of(action, data), action["action"]
        if name == "EXPEDITE_REV_C_PO":
            fees["expedite"] += po["expedite_fee_per_week"] * action["weeks"]
        elif name in ("CANCEL_REV_B_PO", "ALTERNATE_SUPPLIER"):  # resourcing cancels the old order
            fees["cancellation"] += po["cancellation_fee"]
        elif name == "REDUCE_REV_B_PO":
            fees["reduction"] += po["reduction_fee_per_unit"] * action["quantity"]
    return {**fees, "total": sum(fees.values())}


def calculate_excess_value(rev_b_leftover, unit_cost_b, rev_c_closing, unit_cost_c, average_demand):
    """E = leftover Rev B at cost + Rev C above four weeks of demand at cost."""
    excess_b = rev_b_leftover * unit_cost_b
    excess_c = max(0, rev_c_closing - COVERAGE_WEEKS * average_demand) * unit_cost_c
    return excess_b + excess_c
