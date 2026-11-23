"""PuLP (CBC) solver for the same lexicographic plan model, big-M form."""
import pulp

from .model_inputs import MONEY_SCALE, build_model_inputs, chosen_actions, solvable


def _build(inp):
    problem = pulp.LpProblem("changewise", pulp.LpMinimize)
    big, n = inp["big_m"], inp["horizon"]
    y = [pulp.LpVariable(f"y{k}", cat="Binary") for k in range(len(inp["changeovers"]))]
    x = [[pulp.LpVariable(f"x{p}_{o}", cat="Binary") for o in range(len(order["options"]))]
         for p, order in enumerate(inp["orders"])]
    problem += pulp.lpSum(y) == 1
    for row in x:
        problem += pulp.lpSum(row) == 1

    def receipts(t, is_b):
        return pulp.lpSum(
            opt["quantity"] * x[p][o] for p, order in enumerate(inp["orders"]) if order["is_b"] == is_b
            for o, opt in enumerate(order["options"]) if opt["slot"] == t)

    stock_b, stock_c, shortage = inp["stock_b"], inp["stock_c"], []
    for t in range(n):
        use_b, use_c, short, end_b, end_c = (
            pulp.LpVariable(f"{name}{t}", 0, big, cat="Integer") for name in ("ub", "uc", "s", "eb", "ec"))
        c_used = pulp.LpVariable(f"zc{t}", cat="Binary")
        is_short = pulp.LpVariable(f"zs{t}", cat="Binary")
        b_ok = pulp.lpSum(y[k] for k, opt in enumerate(inp["changeovers"]) if opt["b_ok"][t])
        c_ok = pulp.lpSum(y[k] for k, opt in enumerate(inp["changeovers"]) if opt["c_ok"][t])
        problem += use_b + use_c + short == inp["demand"][t]
        problem += end_b == stock_b + receipts(t, True) - use_b
        problem += end_c == stock_c + receipts(t, False) - use_c
        problem += use_b <= big * b_ok
        problem += use_c <= big * c_ok
        problem += use_c <= big * c_used
        problem += short <= big * is_short
        problem += end_b <= big * (1 - c_used) + big * (1 - b_ok)
        problem += end_b <= big * (1 - is_short) + big * (1 - b_ok)
        problem += end_c <= big * (1 - is_short) + big * (1 - c_ok)
        shortage.append(short)
        stock_b, stock_c = end_b, end_c

    over = pulp.LpVariable("over", 0)
    problem += over >= stock_c - inp["coverage_total"] / n
    fees = pulp.lpSum(opt["cost"] * x[p][o] for p, order in enumerate(inp["orders"])
                      for o, opt in enumerate(order["options"]))
    cost = (inp["unit_b"] * stock_b + inp["unit_c"] * over + fees) * (1 / MONEY_SCALE)
    count = pulp.lpSum([len(opt["actions"]) * y[k] for k, opt in enumerate(inp["changeovers"])]
                       + [len(opt["actions"]) * x[p][o] for p, order in enumerate(inp["orders"])
                          for o, opt in enumerate(order["options"])])
    # Each goal is fixed at its optimum plus a tolerance smaller than one unit of that goal.
    return problem, y, x, ((pulp.lpSum(shortage), 0.5), (cost, 0.005), (count, 0.5))


def solve(data, menus, limit=1, time_limit=60):
    """Best `limit` distinct plans as action lists, in lexicographic order (S, E + C, action count)."""
    inp = build_model_inputs(data, menus)
    if not solvable(inp):
        return []
    found, exclusions = [], []
    while len(found) < limit:
        problem, y, x, goals = _build(inp)
        for k, picks in exclusions:
            problem += y[k] + pulp.lpSum(x[p][o] for p, o in enumerate(picks)) <= len(picks)
        for goal, tolerance in goals:
            problem.setObjective(goal)
            problem.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, gapRel=0, gapAbs=0))
            status = pulp.LpStatus[problem.status]
            if status == "Infeasible":
                return found
            if problem.sol_status != pulp.LpSolutionOptimal:
                raise TimeoutError(f"CBC stopped with status {status}")
            problem += goal <= pulp.value(goal) + tolerance
        k = max(range(len(y)), key=lambda i: y[i].value())
        picks = [max(range(len(row)), key=lambda o: row[o].value()) for row in x]
        exclusions.append((k, picks))
        found.append(chosen_actions(inp, k, picks))
    return found
