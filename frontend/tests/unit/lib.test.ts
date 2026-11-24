import { describe, expect, it } from "vitest";
import { authMessage, safePath } from "@/lib/auth";
import { bytes, inr, qty, signed, units, weekRange, words } from "@/lib/format";
import { nextStep } from "@/lib/workflow";
import { niceMax } from "@/components/inventory/MaterialFlow";
import { overview, run } from "./data";

describe("formatting", () => {
  it("writes rupees the Indian way and never turns a missing value into zero", () => {
    expect(inr(92000)).toBe("₹92,000");
    expect(inr(330000)).toBe("₹3,30,000");
    expect([inr(null), qty(undefined), units(null)]).toEqual(["–", "–", "–"]);
    expect([units(1), units(0)]).toEqual(["1 unit", "0 units"]);
  });
  it("writes differences with a sign", () => {
    expect([signed(15), signed(-200), signed(0), signed(null)]).toEqual(["+15", "−200", "no change", "–"]);
  });
  it("turns codes into words and keeps abbreviations", () => {
    expect(words("PRODUCTION_SHORTAGE")).toBe("Production shortage");
    expect(words("REV_B_SCRAP_RISK")).toBe("Rev B scrap risk");
    expect(words("ECN_CONFIRMED")).toBe("ECN confirmed");
    expect(words("PO_WINDOW")).toBe("PO window");
  });
  it("joins weeks into ranges", () => {
    expect(weekRange([6, 7])).toBe("W6–W7");
    expect(weekRange([3, 4, 5, 8])).toBe("W3–W5, W8");
    expect(weekRange([])).toBe("");
  });
  it("sizes", () => expect([bytes(900), bytes(4096), bytes(3 * 1048576)]).toEqual(["900 B", "4 KB", "3.0 MB"]));
  it("rounds an axis up", () => expect([0, 80, 150, 420, 500, 501].map(niceMax)).toEqual([10, 100, 200, 500, 500, 1000]));
});

describe("sign-in helpers", () => {
  it("accepts only a path of this application as the return address", () => {
    expect(safePath("/inventory")).toBe("/inventory");
    for (const bad of ["//evil.example", "https://evil.example", "/\\\\evil", "", null, undefined]) expect(safePath(bad)).toBe("/dashboard");
  });
  it("explains known errors", () => expect(authMessage({ code: "invalid_credentials", message: "x" })).toMatch(/not correct/));
});

describe("next step", () => {
  const review = (status: string) => ({ review_id: "ECNR-1", status, validation_status: "VALID", created_at: "" });
  it("follows the workflow the backend reports", () => {
    expect(nextStep(overview({})).href).toBe("/ecn");
    expect(nextStep(overview({ latest_review: review("NEEDS_REVIEW") })).href).toBe("/ecn/ECNR-1");
    expect(nextStep(overview({ latest_review: review("CONFIRMED") })).permission).toBe("RUN_PLANNING");
    expect(nextStep(overview({ latest_review: review("CONFIRMED"), run })).href).toBe("/approvals/RUN-1");
    expect(nextStep(overview({ latest_review: review("CONFIRMED"), run: { ...run, stale: true } })).label).toBe("Plan again");
    expect(nextStep(overview({ latest_review: review("CONFIRMED"), run: { ...run, recommendations: [] } })).title).toBe("No plan to approve");
    expect(nextStep(overview({ latest_review: { ...review("CONFIRMED"), review_id: "ECNR-2" }, run })).title).toBe("Ready to plan");
    const approval = { approval_id: "A", decision: "APPROVED" as const, modified: false, comment: "", user_name: "", role: "", created_at: "", closed_at: null, plan_id: null, plan_summary: null };
    expect(nextStep(overview({ latest_review: review("CONFIRMED"), run: { ...run, approval } })).title).toBe("Ready to close");
    expect(nextStep(overview({ latest_review: review("CONFIRMED"), run: { ...run, approval: { ...approval, closed_at: "x" } } })).title).toBe("The change is closed");
  });
});
