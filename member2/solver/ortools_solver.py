"""OR-Tools CP-SAT solver for the lexicographic plan model."""
from ortools.sat.python import cp_model

from .model_inputs import build_model_inputs, chosen_actions, solvable


def _build(inp):
    model = cp_model.CpModel()
    big, n = inp["big_m"], inp["horizon"]
    y = [model.new_bool_var(f"y{k}") for k in range(len(inp["changeovers"]))]
    x = [[model.new_bool_var(f"x{p}_{o}") for o in range(len(order["options"]))]
         for p, order in enumerate(inp["orders"])]
    model.add_exactly_one(y)
    for row in x:
        model.add_exactly_one(row)

    def receipts(t, is_b):
        return sum(
            opt["quantity"] * x[p][o] for p, order in enumerate(inp["orders"]) if order["is_b"] == is_b
            for o, opt in enumerate(order["options"]) if opt["slot"] == t)

    stock_b, stock_c, shortage = inp["stock_b"], inp["stock_c"], []
    for t in range(n):
        use_b, use_c, short, end_b, end_c = (
            model.new_int_var(0, big, f"{name}{t}") for name in ("ub", "uc", "s", "eb", "ec"))
        b_used, c_used, is_short = (model.new_bool_var(f"{name}{t}") for name in ("zb", "zc", "zs"))
        model.add(use_b + use_c + short == inp["demand"][t])
        model.add(end_b == stock_b + receipts(t, True) - use_b)
        model.add(end_c == stock_c + receipts(t, False) - use_c)
        model.add(use_b == 0).only_enforce_if(~b_used)
        model.add(use_c == 0).only_enforce_if(~c_used)
        model.add(short == 0).only_enforce_if(~is_short)
        model.add(end_b >= inp["floor_b"]).only_enforce_if(b_used)
        model.add(end_c >= inp["floor_c"]).only_enforce_if(c_used)
        state = {"B": (use_b, b_used, end_b, inp["floor_b"]), "C": (use_c, c_used, end_c, inp["floor_c"])}
        for k, option in enumerate(inp["changeovers"]):
            allowed = option["order"][t]
            for rev, (use, _, end, floor) in state.items():
                if rev in allowed:
                    model.add(end <= floor).only_enforce_if(y[k], is_short)
                else:
                    model.add(use == 0).only_enforce_if(y[k])
            if len(allowed) == 2:  # the second revision only after the first is used up
                first, second = state[allowed[0]], state[allowed[1]]
                model.add(first[2] <= first[3]).only_enforce_if(y[k], second[1])
        shortage.append(short)
        stock_b, stock_c = end_b, end_c

    over = model.new_int_var(0, big * n, "over")  # horizon x (Rev C above coverage)
    model.add(over >= n * stock_c - inp["coverage_total"])
    fees = sum(opt["cost"] * x[p][o] for p, order in enumerate(inp["orders"])
               for o, opt in enumerate(order["options"]))
    late = sum(opt["late_scrap"] * x[p][o] for p, order in enumerate(inp["orders"])
               for o, opt in enumerate(order["options"]))
    cost = n * (inp["unit_b"] * (stock_b + late) + fees) + inp["unit_c"] * over  # whole expression x horizon
    count = (sum(len(opt["actions"]) * y[k] for k, opt in enumerate(inp["changeovers"]))
             + sum(len(opt["actions"]) * x[p][o] for p, order in enumerate(inp["orders"])
                   for o, opt in enumerate(order["options"])))
    return model, y, x, (sum(shortage), cost, count)


def _solve_stage(model, time_limit):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 1  # deterministic
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status == cp_model.INFEASIBLE:
        return None
    if status != cp_model.OPTIMAL:
        raise TimeoutError(f"CP-SAT stopped with status {solver.status_name(status)}")
    return solver


def solve(data, menus, limit=1, time_limit=60):
    """Best `limit` distinct plans as action lists, in lexicographic order (S, E + C, action count)."""
    inp = build_model_inputs(data, menus)
    if not solvable(inp):
        return []
    found, exclusions = [], []
    while len(found) < limit:
        model, y, x, goals = _build(inp)
        for k, picks in exclusions:
            model.add_bool_or([~y[k]] + [~x[p][o] for p, o in enumerate(picks)])
        for goal in goals:
            model.minimize(goal)
            solver = _solve_stage(model, time_limit)
            if solver is None:
                return found
            model.add(goal == solver.value(goal))
        k = next(i for i, var in enumerate(y) if solver.value(var))
        picks = [next(o for o, var in enumerate(row) if solver.value(var)) for row in x]
        exclusions.append((k, picks))
        found.append(chosen_actions(inp, k, picks))
    return found
