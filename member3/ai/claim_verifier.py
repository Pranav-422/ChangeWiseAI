"""Deterministic verification of explanations against engine facts. No LLM is involved.

REJECTED         a number, identifier, rank, status or promise is not supported by the facts
AWAITING_REVIEW  nothing is wrong, but a sentence makes a claim code cannot check
VERIFIED         every claim found was checked and matches
"""
import re

from .fallback_templates import render_sections

VERIFIED, REVIEW, REJECTED = "VERIFIED", "AWAITING_REVIEW", "REJECTED"

_PLAN = re.compile(r"\bPLAN-[0-9A-Za-z]+\b|\bP\d+\b")
_ORDER = re.compile(r"\bPO-\d+\b")
_CHANGE = re.compile(r"\bEC[NRO]-[A-Z0-9-]+\b")
_CODE = re.compile(r"\b[A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+)+\b")  # materials, assemblies, exceptions, runs
_SUPPLIER = re.compile(r"\bS\d+\b")
_WEEK = re.compile(r"\bW(\d{1,2})\b|\bweeks?\s+(\d{1,2})\b", re.I)
_RATIO = re.compile(r"\b(\d+)\s*(?:/|of|out of)\s*(\d+)\b")
_MONEY = re.compile(r"(?:₹|\bRs\.?|\bINR)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:rupees)\b", re.I)
_UNITS = re.compile(r"\b([\d,]+(?:\.\d+)?)\s+(?:\w+\s+){0,2}?units?\b", re.I)
_PERCENT = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:%|percent\b)", re.I)
_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?!\w)")

_MONEY_KEYS = {"excess": r"excess|leftover|scrap|exposure", "action_cost": r"action costs?|fees?",
               "secondary_cost": r"combined|total|secondary"}
_UNIT_KEYS = {"shortage": r"shortages?|unmet|short\b", "stock": r"available|stock|on hand|opening",
              "receipts": r"receipts?|arriv\w*|due|expected", "demand": r"demand",
              "quantity": r"reduc\w*|order"}
_ORDINALS = {"first": 1, "second": 2, "third": 3}
_PROMISE = re.compile(r"\b(guarantee\w*|certainly|definitely|always|never fails?|will save|savings?|risk[- ]free|"
                      r"has been (?:executed|placed|cancelled|expedited)|was (?:executed|placed))\b", re.I)
_UNCHECKABLE = re.compile(r"\b(because|due to|caused by|therefore|as a result|likely|probably|should improve|"
                          r"may|might|could|expect\w* to|two|three|four|five|six|seven|eight|nine|ten|eleven|"
                          r"twelve|\w+teen|twenty|thirty|forty|fifty|hundred|thousand|lakh)\b", re.I)
_ORDER_ACTION = re.compile(r"\b(reduc|cancel|defer|expedit|mov)\w*\s+(?:order\s+|purchase order\s+)?(PO-\d+)"
                           r"(?:\s+by\s+(\d+))?", re.I)
_PLANNER = re.compile(r"\bplanner\b.*\b(decid|approv|review|choos)|\b(decid|approv|review)\w*\b.*\bplanner\b", re.I)
_APPROVED = re.compile(r"\b(?:has been|is|was|already)\s+(?:already\s+)?approved\b", re.I)
_WARNINGS = {
    "NEAR_TIE": r"near[- ]tie", "RESIDUAL_SHORTAGE": r"shortage|unmet", "LOW_ROBUSTNESS": r"robust|stress",
    "NO_FEASIBLE_PLAN": r"no feasible", "INVALID_DATA": r"invalid|conflicting",
}


def _value(text):
    return float(text.replace(",", ""))


def build_verified_facts(engine_results):
    """Flatten one planning run (services.planning_service) into the only facts an explanation may use."""
    dataset, result = engine_results["dataset"], engine_results["result"]
    baseline, bom = engine_results["baseline"], engine_results["bom"]
    change = dataset["engineering_change"]
    weekly = baseline["weekly"] if baseline else []
    plans = {}
    for plan in result["recommendations"]:
        runs = plan["robustness"]
        plans[plan["plan_id"]] = {
            "rank": plan["rank"], "actions": plan["summary"], "effective_week": plan["effective_week"],
            "shortage": plan["shortage_units"], "excess": plan["excess_value"],
            "action_cost": plan["action_cost"], "secondary_cost": plan["secondary_cost"],
            "robustness": {"zero_shortage_runs": runs["numerator"], "total_runs": runs["denominator"],
                           "failed": [{k: s[k] for k in ("lead_time_shock", "demand_shock", "shortage_units")}
                                      for s in runs["scenarios"] if not s["zero_shortage"]]},
            "owners": sorted({engine_results["owners"][a["action"]] for a in plan["actions"]}),
        }
    return {
        "run_id": engine_results["run_id"],
        "decision": result["decision"],
        "recommended_plan_id": result["recommended_plan_id"],
        "approved": engine_results.get("approved", False),
        "change": {"change_id": change.get("change_id"), "old": change.get("old_material_id"),
                   "new": change.get("new_material_id"), "effective_week": change.get("effective_week"),
                   "use_up_end_week": change.get("use_up_end_week"),
                   "assemblies": bom["finished_assemblies"] if bom else []},
        "inventory": {
            "rev_b_available": weekly[0]["rev_b_opening"] if weekly else None,
            "rev_c_available": weekly[0]["rev_c_opening"] if weekly else None,
            "receipts": [{"week": w["week"], "revision": rev, "units": w[f"rev_{rev.lower()}_receipts"]}
                         for w in weekly for rev in "BC" if w[f"rev_{rev.lower()}_receipts"]],
            "demand_by_week": {w["week"]: w["demand"] for w in weekly},
            "shortage": baseline["total_shortage"] if baseline else None,
            "shortage_by_week": {w["week"]: w["shortage"] for w in weekly if w["shortage"]},
            "excess": baseline["total_excess_value"] if baseline else None,
        },
        "plans": plans,
        "counts": result["counts"],
        "rejected": [{"plan_id": p["plan_id"], "rules": sorted({r["rule"] for r in p["rejection_reasons"]})}
                     for p in result["rejected_plans"]],
        "escalations": [{"code": e["code"], "plan_ids": e["plan_ids"], "message": e["message"]}
                        for e in result["escalations"]],
        "data_errors": [e["description"] for esc in result["escalations"] if esc["code"] == "INVALID_DATA"
                        for e in esc["evidence"]],
        "suppliers": {s["supplier_id"]: s["status"] for s in dataset["suppliers"]},
        "orders": sorted(p["po_id"] for p in dataset["purchase_orders"]),
        "order_quantities": sorted({p["quantity"] for p in dataset["purchase_orders"] if "quantity" in p}),
        "exceptions": [{k: e[k] for k in ("exception_id", "type", "band", "week", "units", "impact_rs",
                                          "severity", "description")} for e in engine_results["exceptions"]],
    }


def extract_explanation_claims(explanation):
    """One record per sentence: identifiers, numbers by kind, and wording that needs a check."""
    claims = []
    for sentence in re.split(r"(?<=[.!?])(?<!\bRs\.)\s+|\n+", explanation):
        sentence = sentence.strip()
        if not sentence:
            continue
        claim = {"sentence": sentence, "plans": _PLAN.findall(sentence), "orders": _ORDER.findall(sentence),
                 "changes": _CHANGE.findall(sentence), "codes": [
                     c for c in _CODE.findall(sentence)
                     if not any(p.fullmatch(c) for p in (_PLAN, _ORDER, _CHANGE))], "suppliers": _SUPPLIER.findall(sentence),
                 "weeks": [int(a or b) for a, b in _WEEK.findall(sentence)], "ratios": [],
                 "money": [], "units": [], "percents": [], "numbers": []}
        rest = sentence
        for pattern in (_PLAN, _ORDER, _CHANGE, _CODE, _SUPPLIER, _WEEK):
            rest = pattern.sub(lambda m: " " * len(m[0]), rest)
        for kind, pattern in (("money", _MONEY), ("ratios", _RATIO), ("units", _UNITS),
                              ("percents", _PERCENT), ("numbers", _NUMBER)):
            for match in pattern.finditer(rest):
                groups = [g for g in match.groups() if g] or [match[0]]
                value = tuple(int(g) for g in groups) if kind == "ratios" else _value(groups[0])
                claim[kind].append({"value": value, "start": match.start(), "end": match.end()})
            # blank digits only, so keywords next to a number stay visible to later patterns
            rest = pattern.sub(lambda m: re.sub(r"[\d,.]", " ", m[0]), rest)
        claims.append(claim)
    return claims


def _scope(claim, facts):
    """Which plan (or the do-nothing baseline) a sentence talks about."""
    for plan_id in claim["plans"]:
        if plan_id in facts["plans"]:
            return facts["plans"][plan_id]
    if re.search(r"\bwithout (?:any )?(?:corrective )?action|baseline|if nothing (?:changes|is done)", claim["sentence"], re.I):
        return {"shortage": facts["inventory"]["shortage"], "excess": facts["inventory"]["excess"],
                "action_cost": 0, "secondary_cost": facts["inventory"]["excess"], "baseline": True}
    return facts["plans"].get(facts["recommended_plan_id"])


def _keyword(sentence, item, keys):
    """Nearest keyword: right after the number, else the last one before it, else the first after it."""
    after = sentence[item["end"]:]
    for name, pattern in keys.items():
        if re.match(rf"\W*(?:units?\W+)?(?:of\W+|in\W+)?(?:{pattern})", after, re.I):
            return name
    before = [(m.start(), n) for n, p in keys.items()
              for m in re.finditer(rf"\b(?:{p})", sentence[:item["start"]], re.I)]
    if before:
        return max(before)[1]
    behind = [(m.start(), n) for n, p in keys.items() for m in re.finditer(rf"\b(?:{p})", after, re.I)]
    return min(behind)[1] if behind else None


def _failure(claim, kind, detail):
    return {"sentence": claim["sentence"], "kind": kind, "detail": detail}


def verify_numeric_claims(claims, facts):
    inventory, exceptions = facts["inventory"], facts["exceptions"]
    weeks = {facts["change"]["effective_week"], facts["change"]["use_up_end_week"],
             *inventory["demand_by_week"], *(p["effective_week"] for p in facts["plans"].values()),
             *(e["week"] for e in exceptions)}
    by_action = {int(n) for p in facts["plans"].values() for n in re.findall(r"by (\d+)(?! wk)", p["actions"])}
    failures = []
    for claim in claims:
        sentence, scope = claim["sentence"], _scope(claim, facts)
        shortage = {scope["shortage"]} if scope else set()
        if scope is None or scope.get("baseline"):
            shortage |= set(inventory["shortage_by_week"].values())
        stress = re.search(r"stress|delay|demand (?:is|rises|at|of)|shock", sentence, re.I)
        if stress and scope and "robustness" in scope:
            shortage |= {r["shortage_units"] for r in scope["robustness"]["failed"]}
        exception_scope = re.search(r"exception|severity|critical", sentence, re.I)
        if exception_scope:
            shortage |= {e["units"] for e in exceptions}
        units = {"shortage": shortage,
                 "stock": {inventory["rev_b_available"], inventory["rev_c_available"]},
                 "receipts": {r["units"] for r in inventory["receipts"]},
                 "demand": set(inventory["demand_by_week"].values()),
                 "quantity": by_action | set(facts["order_quantities"])}
        for item in claim["money"]:
            key = _keyword(sentence, item, _MONEY_KEYS)
            if exception_scope:
                allowed = {e["impact_rs"] for e in exceptions} | {e["severity"] for e in exceptions}
            elif key is None or scope is None:
                allowed = set()
            else:
                allowed = {scope[key]}
            if item["value"] not in allowed:
                failures.append(_failure(claim, "money", f"{item['value']:g} as {key or 'unknown amount'}"))
        for item in claim["units"]:
            key = _keyword(sentence, item, _UNIT_KEYS)
            if item["value"] not in units.get(key, set()):
                failures.append(_failure(claim, "units", f"{item['value']:g} as {key or 'unknown quantity'}"))
        for item in claim["ratios"]:
            robust = scope.get("robustness") if scope else None
            if not robust or item["value"] != (robust["zero_shortage_runs"], robust["total_runs"]):
                failures.append(_failure(claim, "robustness", "%d of %d" % item["value"]))
        for week in claim["weeks"]:
            if week not in weeks:
                failures.append(_failure(claim, "week", f"W{week}"))
        for item in claim["percents"]:
            shocks = {round(abs(r["demand_shock"]) * 100) for p in facts["plans"].values()
                      for r in p["robustness"]["failed"]}
            if item["value"] not in shocks:
                failures.append(_failure(claim, "percent", f"{item['value']:g}%"))
        counts = {v for k, v in facts["counts"].items()} | {len(facts["exceptions"])}
        counts |= {r["lead_time_shock"] for p in facts["plans"].values() for r in p["robustness"]["failed"]}
        for item in claim["numbers"]:
            near = sentence[item["end"]:item["end"] + 40]
            described = re.match(r"\W*(?:combinations?|candidates?|feasible|rejected|plans?|exceptions?|weeks?|wk)",
                                 near, re.I)
            action = item["value"] in by_action and re.search(r"\b(by|reduc\w*)\W*$", sentence[:item["start"]], re.I)
            one_week = re.search(r"\bby\W*$", sentence[:item["start"]], re.I) and re.match(r"\s*wk", near) and any(
                f"by {item['value']:g} wk" in p["actions"] for p in facts["plans"].values())
            if not (action or one_week or (described and item["value"] in counts)):
                failures.append(_failure(claim, "number", f"{item['value']:g}"))
        if scope and re.search(r"\b(?:no|zero)\s+(?:\w+\s+){0,3}?(?:shortage|unmet)", sentence, re.I):
            stress_sentence = claim["ratios"] or stress
            if scope["shortage"] != 0 and not stress_sentence:
                failures.append(_failure(claim, "shortage", "states zero shortage"))
    return failures


def verify_plan_claims(claims, facts):
    known = set(facts["plans"]) | {r["plan_id"] for r in facts["rejected"]} | {
        i for e in facts["escalations"] for i in e["plan_ids"]}
    failures = []
    for claim in claims:
        sentence = claim["sentence"]
        failures += [_failure(claim, "plan_id", p) for p in claim["plans"] if p not in known]
        if len(claim["plans"]) == 1 and claim["plans"][0] in facts["plans"]:
            rank = facts["plans"][claim["plans"][0]]["rank"]
            stated = [n for w, n in _ORDINALS.items() if re.search(rf"ranks?\s+{w}|{w}[- ]ranked", sentence, re.I)]
            if re.search(r"\b(highest[- ]ranked|top[- ]ranked|recommended plan|best plan|best feasible)\b", sentence, re.I):
                stated.append(1)
            if any(n != rank for n in stated):
                failures.append(_failure(claim, "rank", f"plan has rank {rank}"))
        rejected = {r["plan_id"] for r in facts["rejected"]}
        for plan_id in claim["plans"]:
            if plan_id in rejected and re.search(r"\bfeasible\b|recommend", sentence, re.I):
                failures.append(_failure(claim, "feasibility", f"{plan_id} is rejected"))
            if plan_id in facts["plans"] and re.search(r"\b(?:breaks|violates)\b(?!\s+no\b)|\bis rejected", sentence, re.I):
                failures.append(_failure(claim, "hard_rule", f"{plan_id} is feasible"))
        if re.search(r"\brecommended plan\b", sentence, re.I) and not facts["recommended_plan_id"] \
                and not re.search(r"\bno\b", sentence, re.I):
            failures.append(_failure(claim, "plan", "no plan is recommended"))
        if _APPROVED.search(sentence) and not claim["suppliers"] and not claim["changes"] \
                and not re.search(r"\b(?:not|until|once|unless|before)\b", sentence, re.I) and not facts["approved"]:
            failures.append(_failure(claim, "approval", "no plan has been approved"))
    return failures


def verify_risk_claims(claims, facts):
    """Suppliers, orders, promises, and warnings that must not be left out."""
    failures = []
    codes = {facts["change"]["old"], facts["change"]["new"], *facts["change"]["assemblies"], facts["run_id"],
             *(e["exception_id"] for e in facts["exceptions"])}
    for claim in claims:
        sentence = claim["sentence"]
        failures += [_failure(claim, "code", c) for c in claim["codes"] if c not in codes]
        failures += [_failure(claim, "order", o) for o in claim["orders"] if o not in facts["orders"]]
        failures += [_failure(claim, "change", c) for c in claim["changes"] if c != facts["change"]["change_id"]]
        for supplier in claim["suppliers"]:
            status = facts["suppliers"].get(supplier)
            if status is None:
                failures.append(_failure(claim, "supplier", f"{supplier} is unknown"))
                continue
            for word, meaning in (("blocked", "BLOCKED"), ("unqualified", "UNQUALIFIED"), ("approved", "APPROVED")):
                if re.search(rf"\b{supplier}\b[^.;]*?\bis\s+(not\s+)?{word}\b", sentence, re.I):
                    denied = bool(re.search(rf"\bis\s+not\s+{word}\b", sentence, re.I))
                    if (status == meaning) == denied:
                        failures.append(_failure(claim, "supplier", f"{supplier} is {status}"))
        for verb, order, amount in _ORDER_ACTION.findall(sentence):
            stated = rf"{verb}\w*\s+{order}" + (rf"\s+by\s+{amount}\b" if amount else r"\b")
            scope = [facts["plans"][p] for p in claim["plans"] if p in facts["plans"]] or facts["plans"].values()
            if not any(re.search(stated, p["actions"], re.I) for p in scope):
                failures.append(_failure(claim, "action", f"no plan contains {verb} {order} {amount}".strip()))
        for match in _PROMISE.finditer(sentence):
            failures.append(_failure(claim, "unsupported_promise", match[0]))
    text = " ".join(c["sentence"] for c in claims)
    for record in facts["escalations"]:
        if not re.search(_WARNINGS[record["code"]], text, re.I):
            failures.append({"sentence": "", "kind": "missing_warning", "detail": record["code"]})
    if facts["plans"] and not facts["approved"] and not re.search(r"planner", text, re.I):
        failures.append({"sentence": "", "kind": "missing_warning", "detail": "planner approval"})
    return failures


def _needs_review(claim, template_sentences):
    """True when code cannot confirm what the sentence says."""
    sentence = claim["sentence"]
    if sentence in template_sentences or (_PLANNER.search(sentence) and not _UNCHECKABLE.search(sentence)):
        return False
    if _UNCHECKABLE.search(sentence):
        return True
    if claim["suppliers"] and not re.search(r"\bis\s+(?:not\s+)?(?:blocked|unqualified|approved)\b", sentence, re.I):
        return True
    checked = any(claim[k] for k in ("plans", "orders", "changes", "codes", "suppliers", "weeks", "ratios", "money",
                                     "units", "percents", "numbers"))
    return not checked and not re.search(r"\b(?:no|zero)\s+(?:\w+\s+){0,3}?(?:shortage|unmet)", sentence, re.I)


def verify_explanation(explanation, facts):
    claims = extract_explanation_claims(explanation)
    failures = (verify_numeric_claims(claims, facts) + verify_plan_claims(claims, facts)
                + verify_risk_claims(claims, facts))
    trusted = {c["sentence"] for c in extract_explanation_claims("\n".join(render_sections(facts).values()))}
    review = [c["sentence"] for c in claims if _needs_review(c, trusted)]
    status = REJECTED if failures or not claims else REVIEW if review else VERIFIED
    return {"status": status, "failures": failures, "needs_review": review, "sentences": len(claims)}
