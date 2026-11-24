import type { Overview } from "@/lib/api";

export type NextStep = { title: string; detail: string; href: string; label: string; permission: string };

/** The one thing the workflow is waiting for. Reads the state the backend reports; decides nothing. */
export function nextStep(o: Overview): NextStep {
  const review = o.latest_review, run = o.run;
  if (!review) return { title: "The ECN document is missing", detail: "Nothing can be planned before the engineering change notice is read and confirmed.", href: "/ecn", label: "Open ECN intake", permission: "SUBMIT_ECN" };
  if (review.status !== "CONFIRMED") return { title: "The ECN needs a person", detail: "Compare the extracted fields with the document, correct them and confirm.", href: `/ecn/${review.review_id}`, label: "Review the ECN", permission: "SUBMIT_ECN" };
  if (!run || run.review_id !== review.review_id) return { title: "Ready to plan", detail: "The ECN is confirmed. Run the optimization on the current records.", href: `/ecn/${review.review_id}`, label: "Go to planning", permission: "RUN_PLANNING" };
  if (!run.approval && run.stale) return { title: "Records changed since the plan", detail: "The last run used older records, so it cannot be approved. Plan again.", href: `/ecn/${review.review_id}`, label: "Plan again", permission: "RUN_PLANNING" };
  if (!run.approval) return run.recommendations.length
    ? { title: "A planner has to decide", detail: "The engine has a proposal. Nothing happens until a planner approves or rejects it.", href: `/approvals/${run.run_id}`, label: "Review the proposal", permission: "DECIDE_PLAN" }
    : { title: "No plan to approve", detail: run.escalations[0]?.message ?? "The engine found no feasible plan.", href: "/optimization", label: "See why", permission: "VIEW" };
  if (run.approval.decision === "REJECTED") return { title: "The proposal was rejected", detail: run.approval.comment, href: "/what-if", label: "Try a scenario", permission: "RUN_WHAT_IF" };
  if (run.approval.closed_at) return { title: "The change is closed", detail: "Every approved action is done and the change was closed.", href: "/audit", label: "See the history", permission: "VIEW_AUDIT" };
  const open = o.actions.filter((a) => a.status !== "DONE").length;
  return open
    ? { title: `${open} ${open === 1 ? "action is" : "actions are"} open`, detail: "The approved plan is with the teams that carry it out.", href: "/actions", label: "Open the tracker", permission: "VIEW" }
    : { title: "Ready to close", detail: "Every action is done. A planner can close the change.", href: "/actions", label: "Close the change", permission: "CLOSE_CHANGE" };
}
