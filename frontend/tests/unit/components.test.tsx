import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExplanationPanel } from "@/components/ai/ExplanationPanel";
import { LineageExplorer } from "@/components/bom/LineageExplorer";
import { DocumentText } from "@/components/engineering/DocumentText";
import { RevisionRibbon } from "@/components/engineering/RevisionRibbon";
import { StageTrack } from "@/components/engineering/StageTrack";
import { SeverityRail } from "@/components/exceptions/SeverityRail";
import { MaterialFlow } from "@/components/inventory/MaterialFlow";
import { DecisionPanel } from "@/components/optimization/DecisionPanel";
import { RobustnessMatrix } from "@/components/optimization/RobustnessMatrix";
import { Pager, Tabs } from "@/components/ui/overlay";
import { Loaded } from "@/components/ui/primitives";
import { ApiError } from "@/lib/api/errors";
import type { BomImpact, ExceptionItem } from "@/lib/api";
import { explanation, run, week } from "./data";

describe("decision panel", () => {
  it("shows the engine's plan as a proposal that awaits a person", () => {
    render(<DecisionPanel run={run} />);
    expect(screen.getByText("Awaiting planner decision")).toBeInTheDocument();
    expect(screen.queryByText(/approved/i)).not.toBeInTheDocument();
    expect(screen.getByText("₹17,000")).toBeInTheDocument();
    const text = screen.getByRole("article").textContent!;
    expect(text.indexOf("unmet demand (S)")).toBeLessThan(text.indexOf("(E + C)")); // the order of the objective
  });
  it("says who decided", () => {
    render(<DecisionPanel run={{ ...run, approval: { approval_id: "A", decision: "REJECTED", modified: false, comment: "no", user_name: "Asha", role: "Planner", created_at: "", closed_at: null, plan_id: null, plan_summary: null } }} />);
    expect(screen.getByText("Rejected by Asha")).toBeInTheDocument();
  });
  it("shows no numbers when there is no plan", () => {
    render(<DecisionPanel run={{ ...run, decision: "NO_FEASIBLE_PLAN", recommendations: [] }} />);
    expect(screen.getAllByText("No feasible plan").length).toBeGreaterThan(0);
    expect(screen.queryByText(/₹/)).not.toBeInTheDocument();
  });
});

describe("explanation", () => {
  it("always says where the words come from and that the planner decides", () => {
    const { rerender } = render(<ExplanationPanel explanation={explanation} />);
    expect(screen.getByText("Template, filled from engine facts")).toBeInTheDocument();
    rerender(<ExplanationPanel explanation={{ ...explanation, label: "AI_GENERATED_VERIFIED" }} />);
    expect(screen.getByText("AI-generated, checked against engine facts")).toBeInTheDocument();
    rerender(<ExplanationPanel explanation={{ ...explanation, label: "AWAITING_REVIEW", draft: [{ title: "Risks", text: "It may slip." }], warning: "Check it." }} />);
    expect(screen.getByText("AI draft, not verified")).toBeInTheDocument();
    expect(screen.getByText(/the planner decides/)).toBeInTheDocument();
  });
});

describe("material flow", () => {
  const weeks = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => week(n, n === 7 ? { shortage: 40, rev_c_usage: 60 } : {}));
  it("describes the weeks to a screen reader and on focus", () => {
    render(<MaterialFlow weeks={weeks} effectiveWeek={6} useUpEnd={5} oldRevision="Rev B" newRevision="Rev C" />);
    expect(screen.getByRole("img")).toHaveAccessibleName(/not met in W7/);
    const column = screen.getByRole("button", { name: /^Week 7: demand 100, unmet 40/ });
    fireEvent.focus(column);
    expect(within(screen.getByRole("status")).getByText("Unmet")).toBeInTheDocument();
  });
  it("marks old stock that may no longer be used", () => {
    render(<MaterialFlow weeks={weeks} effectiveWeek={6} useUpEnd={5} oldRevision="Rev B" newRevision="Rev C" />);
    expect(screen.getByText("Rev B not usable")).toBeInTheDocument();
  });
  it("draws nothing without data", () => {
    const { container } = render(<MaterialFlow weeks={[]} effectiveWeek={6} useUpEnd={5} oldRevision="Rev B" newRevision="Rev C" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("revision ribbon", () => {
  const base = { from: "Rev B", to: "Rev C", horizon: 8, interchangeable: true };
  it("names a gap with no permitted revision", () => {
    render(<RevisionRibbon {...base} effectiveWeek={6} useUpEnd={3} />);
    expect(screen.getByText(/No revision is permitted from W4 to W5/)).toBeInTheDocument();
  });
  it("names an overlap", () => {
    render(<RevisionRibbon {...base} effectiveWeek={5} useUpEnd={6} />);
    expect(screen.getByText(/Both revisions may be used from W5 to W6/)).toBeInTheDocument();
  });
});

const exception = (over: Partial<ExceptionItem>): ExceptionItem => ({
  exception_id: "E1", simulation_id: "S", change_id: "ECN-001", exception_type: "PRODUCTION_SHORTAGE", material_id: "MAT-102", week: 6, quantity: 150, financial_impact: 300000,
  severity_score: 90, severity_level: "CRITICAL", severity_rank: 1, description: "d", recommended_action: "a", owner_role: "Production Planning", owner_roles: ["Planner"], status: "OPEN", allowed_statuses: [], updated_at: null, ...over });

describe("severity rail", () => {
  it("keeps the order it is given", () => {
    render(<SeverityRail items={[exception({}), exception({ exception_id: "E2", severity_level: "LOW", exception_type: "DATA_REVIEW", severity_rank: 2 })]} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Critical");
    expect(items[1]).toHaveTextContent("Data review");
  });
});

describe("robustness", () => {
  it("shows every stress run with its outcome in words", () => {
    render(<RobustnessMatrix robustness={run.recommendations[0]!.robustness!} caption="Plan 1" />);
    expect(screen.getAllByText("Covered")).toHaveLength(3);
    expect(screen.getAllByText("200 short")).toHaveLength(3);
  });
});

describe("document text", () => {
  it("marks quotes across line breaks and treats the document as text", () => {
    const { container } = render(<DocumentText text={"Effective\n  week: W6 <b>x</b>"} evidence={{ effective_week: "Effective week: W6" }} active="effective_week" />);
    expect(container.querySelector("mark")!.textContent).toBe("Effective\n  week: W6");
    expect(container.querySelector("b")).toBeNull();
  });
  it("ignores characters that are special in patterns", () => {
    const { container } = render(<DocumentText text="Cost (net) [x] +5" evidence={{ reason: "Cost (net) [x] +5" }} active={null} />);
    expect(container.querySelector("mark")).not.toBeNull();
  });
});

const bom: BomImpact = {
  change_id: "ECN-001", old_material_id: "MAT-101", new_material_id: "MAT-102", impact_status: "IDENTIFIED", direct_parents: ["SUB-201"], indirect_parents: ["PUMP-001"], finished_products: ["PUMP-001"], cycles: [],
  nodes: ["MAT-101", "MAT-102", "SUB-201", "PUMP-001"].map((m) => ({ material_id: m, name: `Name ${m}`, type: "ASSEMBLY", revision: "Rev B", status: "Active", description: null })),
  edges: [{ parent: "SUB-201", child: "MAT-101", quantity: 1, effective_from: 1, effective_to: 5 }, { parent: "SUB-201", child: "MAT-102", quantity: 1, effective_from: 6, effective_to: null }, { parent: "PUMP-001", child: "SUB-201", quantity: 1, effective_from: 1, effective_to: null }],
  paths: [{ material_id: "MAT-101", assembly: "PUMP-001", assembly_type: "FINISHED", path_ids: ["PUMP-001", "SUB-201", "MAT-101"], quantity: 1 }],
};

describe("BOM lineage", () => {
  it("collapses and expands what a material is used in", () => {
    render(<LineageExplorer bom={bom} />);
    expect(screen.getByRole("button", { name: /PUMP-001 Name/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hide what uses SUB-201" }));
    expect(screen.queryByRole("button", { name: /PUMP-001 Name/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Expand everything" }));
    fireEvent.click(screen.getByRole("button", { name: /PUMP-001 Name/ }));
    expect(screen.getByRole("complementary")).toHaveTextContent("Name PUMP-001");
  });
  it("does not hang on a cycle", () => {
    render(<LineageExplorer bom={{ ...bom, edges: [...bom.edges, { parent: "MAT-101", child: "PUMP-001", quantity: 1, effective_from: 1, effective_to: null }] }} />);
    expect(screen.getByRole("region")).toBeInTheDocument();
  });
});

describe("building blocks", () => {
  it("shows loading, failure and data", () => {
    const retry = vi.fn();
    const { rerender } = render(<Loaded<string> data={undefined} error={undefined}>{(d) => <p>{d}</p>}</Loaded>);
    expect(screen.getByRole("status")).toBeInTheDocument();
    rerender(<Loaded<string> data={undefined} error={new ApiError(503, "X", "Down")} retry={retry}>{(d) => <p>{d}</p>}</Loaded>);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();
    rerender(<Loaded data="here" error={undefined}>{(d) => <p>{d}</p>}</Loaded>);
    expect(screen.getByText("here")).toBeInTheDocument();
  });
  it("moves between tabs with the arrow keys", () => {
    render(<Tabs label="t" tabs={[{ id: "a", title: "A", content: "one" }, { id: "b", title: "B", content: "two" }]} />);
    fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
    expect(screen.getByRole("tabpanel")).toHaveTextContent("two");
  });
  it("hides paging when one page is enough", () => {
    const { container, rerender } = render(<Pager total={5} limit={10} offset={0} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<Pager total={25} limit={10} offset={20} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
  it("marks the current stage", () => {
    render(<StageTrack done={2} />);
    expect(screen.getByText("Plan approved").closest("li")).toHaveAttribute("aria-current", "step");
  });
});
