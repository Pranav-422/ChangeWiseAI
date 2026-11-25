import type { Explanation, Overview, Run, Week } from "@/lib/api";

export const week = (n: number, over: Partial<Week> = {}): Week => ({
  week: n, demand: 100, shortage: 0, applicable_revision: n < 6 ? "B" : "C",
  rev_b_opening: 300, rev_b_receipts: 0, rev_b_reserved: 0, rev_b_available: 300, rev_b_safety_stock: 30, rev_b_usable: 270, rev_b_usage: n < 6 ? 100 : 0, rev_b_closing: 200,
  rev_c_opening: 0, rev_c_receipts: 0, rev_c_reserved: 0, rev_c_available: 0, rev_c_safety_stock: 20, rev_c_usable: 0, rev_c_usage: n < 6 ? 0 : 100, rev_c_closing: 50, ...over,
});

const nine = [0, 1, 2].flatMap((lead) => [-0.1, 0, 0.1].map((demand) => ({
  scenario_id: `${lead}${demand}`, lead_time_shock: lead, demand_shock: demand, shortage_units: lead * 100, excess_value: 0, zero_shortage: lead === 0 })));

export const run: Run = {
  run_id: "RUN-1", review_id: "ECNR-1", change_id: "ECN-001", scenario_id: "base", input_hash: "a", config_hash: "b", engine_version: "1", simulator: "s",
  method: "ENUMERATION", decision: "ESCALATED", requires_planner_review: true, recommended_plan_id: "PLAN-1",
  counts: { combinations: 10, candidates: 12, feasible: 10, rejected: 2 },
  recommendations: [{ plan_id: "PLAN-1", rank: 1, overall_rank: 1, effective_week: 6, actions: [], summary: "Reduce PO-001 by 200", shortage_units: 0, excess_value: 12000, action_cost: 5000,
    action_cost_breakdown: { expedite: 0, cancellation: 0, reduction: 5000, total: 5000 }, secondary_cost: 17000, feasibility: "FEASIBLE", near_ties: [], simulation_reference: "SIM",
    robustness: { numerator: 3, denominator: 9, display: "3/9", scenarios: nine }, weekly: [week(1)] }],
  near_ties: [], escalations: [{ code: "NEAR_TIE", message: "Nearly equal.", plan_ids: [], evidence: [], status: "PLANNER_REVIEW_REQUIRED" }],
  effective_week_comparison: [], hard_rules: [{ rule: "PO_WINDOW", title: "Windows", violations: 2 }, { rule: "INPUT_VALIDITY", title: "Data", violations: 0 }],
  computation_seconds: 1, created_by: "Asha", created_at: "2026-11-24T10:00:00+00:00", stale: false, newest: true, approval: null,
};

export const explanation: Explanation = {
  explanation_id: "E", subject_type: "RUN", subject_id: "RUN-1", label: "TEMPLATE_GENERATED", source: "templates",
  sections: [{ title: "Recommendation", text: "PLAN-1 ranks first." }], draft: null, warning: null, facts: {}, verification_status: "NOT_APPLICABLE", verification: null, created_at: "2026-11-24T10:00:00+00:00",
};

export const overview = (over: Partial<Overview>): Overview => ({
  stage: 0, latest_review: null, run: null, actions: [], exceptions: [], finished_products: [], pending_approvals: 0, recent_events: [], scenario_id: "base", scenarios: [],
  ...over,
} as Overview);
