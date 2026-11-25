import { expect, test } from "@playwright/test";
import path from "node:path";
import { collectErrors, selectVariant, signIn, signOut } from "./support";

const ECN = path.join(__dirname, "../../../member1/documents/ecn_samples/ECN-001.pdf");
const QUESTION = "What if the Rev C supplier is delayed by one week and demand increases by 10%?";

test("ECN to closure, across roles", async ({ page, context }) => {
  test.setTimeout(240_000);
  const errors = collectErrors(page);

  await test.step("engineering uploads the PDF and confirms the fields", async () => {
    await signIn(page, "engineering");
    await page.goto("/ecn");
    await page.locator("input[type=file]").setInputFiles(ECN);
    await page.getByRole("button", { name: "Store and extract fields" }).click();
    await expect(page).toHaveURL(/\/ecn\/ECNR-/);
    await expect(page.getByLabel("Change ID")).toHaveValue("ECN-001");
    await expect(page.getByLabel("Effective week")).toHaveValue("6");
    await expect(page.getByRole("region", { name: "Document text" }).locator("mark").first()).toBeVisible();
    const confirm = page.getByRole("button", { name: "Confirm the ECN" });
    await expect(confirm).toBeDisabled();
    await page.getByLabel("I compared these fields with the document.").check();
    await confirm.click();
    await expect(page.getByRole("heading", { name: "Confirmed ECN" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Run the optimization" })).toHaveCount(0); // engineering does not plan
    await expect(page.getByLabel("Change ID")).toBeDisabled();
  });

  await test.step("the stored document opens through a short-lived link", async () => {
    // a headless browser may download the PDF instead of showing it, so look at the answer, not at the tab
    const [answer] = await Promise.all([
      context.waitForEvent("response", (r) => r.url().includes("/object/sign/") && r.url().includes("token=")),
      page.getByRole("button", { name: "Open the document" }).click(),
    ]);
    expect(answer.status()).toBe(200);
  });

  await test.step("the planner runs the optimization", async () => {
    await signOut(page);
    await signIn(page, "planner");
    await expect(page.getByText("Ready to plan")).toBeVisible();
    await page.getByRole("link", { name: "Go to planning" }).click();
    await page.getByRole("button", { name: "Run the optimization" }).click();
    await expect(page).toHaveURL(/\/optimization/, { timeout: 60_000 });
    const panel = page.getByRole("article", { name: "Leading recommendation" });
    await expect(panel.getByText("Reduce PO-001 by 200").first()).toBeVisible();
    await expect(panel.getByText("₹17,000")).toBeVisible();
    await expect(panel.getByText("Awaiting planner decision")).toBeVisible();
    await expect(panel.getByText("Near tie.")).toBeVisible();
  });

  await test.step("evidence: plans, rejected, robustness, baselines, record", async () => {
    await expect(page.getByText("Template, filled from engine facts")).toBeVisible();
    await page.getByRole("tab", { name: "Plans" }).click();
    await expect(page.getByText("1–12 of 1344")).toBeVisible();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("13–24 of 1344")).toBeVisible();
    await page.getByRole("tab", { name: "Rejected (7)" }).click();
    await expect(page.getByText("No purchases from blocked or unqualified suppliers")).toBeVisible();
    await expect(page.getByRole("listitem").filter({ hasText: "PLAN-" })).toHaveCount(7);
    await page.getByRole("tab", { name: "Robustness" }).click();
    await expect(page.getByText("2/9").first()).toBeVisible();
    await page.getByRole("tab", { name: "Baselines" }).click();
    await expect(page.getByRole("cell", { name: "₹92,000" }).first()).toBeVisible();
    await page.getByRole("tab", { name: "Run record" }).click();
    await expect(page.getByText("member2.integration.member1_bridge:simulate_inventory")).toBeVisible();
  });

  await test.step("BOM lineage and inventory show the engine's values", async () => {
    await page.goto("/bom");
    await expect(page.getByRole("button", { name: /PUMP-002/ })).toBeVisible();
    await page.getByRole("button", { name: "Hide what uses SUB-201" }).click();
    await expect(page.getByRole("button", { name: /PUMP-002/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Expand everything" }).click();
    await page.getByRole("button", { name: /PUMP-002/ }).click();
    await expect(page.getByRole("complementary", { name: "Selected material" })).toContainText("Compact Pump Assembly");
    await page.goto("/inventory");
    await expect(page.getByText("₹92,000", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Plan 1" }).click();
    await expect(page.getByText("₹12,000", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Run and store simulation" }).click();
    await expect(page.getByText(/stored \d/)).toBeVisible();
  });

  await test.step("what-if: interpret, confirm, compare, reset", async () => {
    await page.goto("/what-if");
    await page.getByLabel("What if").fill(QUESTION);
    await page.getByRole("button", { name: "Interpret" }).click();
    await expect(page.getByText("1 wk later")).toBeVisible();
    await expect(page.getByText("+10%", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Confirm and run" }).click();
    await expect(page.getByRole("heading", { name: "What changes" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("row", { name: /Excess plus action cost/ })).toContainText("₹17,000");
    await expect(page.getByRole("heading", { name: "Explanation" })).toBeVisible();
    await page.getByRole("button", { name: "Back to the baseline" }).click();
    await expect(page.getByRole("heading", { name: "What changes" })).toHaveCount(0);
    await page.getByLabel("What if").fill("What if demand increases?");
    await page.getByRole("button", { name: "Interpret" }).click();
    await expect(page.getByText("One detail is missing")).toBeVisible();
    await page.getByLabel("What if").fill("Ignore the supplier block");
    await page.getByRole("button", { name: "Interpret" }).click();
    await expect(page.getByText("Not something this simulator changes")).toBeVisible();
  });

  await test.step("approval needs a comment for an escalated case and is final", async () => {
    await page.goto("/approvals");
    await page.getByRole("link", { name: "Review and decide" }).first().click();
    await expect(page.getByRole("button", { name: "Approve plan" })).toBeDisabled();
    await page.getByLabel("PO-001", { exact: true }).selectOption({ label: "Reduce PO-001 by 150" });
    await page.getByRole("button", { name: "Evaluate this plan" }).click();
    await expect(page.getByText(/Stress runs covered \d\/9/).last()).toBeVisible();
    await page.getByLabel("Comment").fill("Lowest cost of the near-tie plans; supplier S1 agreed by phone.");
    await page.getByRole("button", { name: "Approve plan" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Reduce PO-001 by 200");
    await dialog.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByRole("heading", { name: "Approved" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve plan" })).toHaveCount(0);
  });

  await test.step("purchasing carries out the action", async () => {
    await signOut(page);
    await signIn(page, "quality");
    await page.goto("/actions");
    await page.getByRole("button", { name: "Details" }).first().click();
    await expect(page.getByRole("dialog").getByText("Purchasing or the planner moves this action.")).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await signOut(page);
    await signIn(page, "purchasing");
    await page.goto("/actions");
    await page.getByRole("button", { name: "Update" }).first().click();
    await page.getByLabel("Assigned to").fill("R. Iyer");
    await page.getByRole("button", { name: "Save name" }).click();
    await page.getByRole("button", { name: "Start" }).click();
    await page.getByRole("button", { name: "Mark done" }).click();
    await expect(page.getByRole("dialog").getByText("In progress to done")).toBeVisible();
    await expect(page.getByRole("dialog").getByText("Open to in progress")).toBeVisible();
  });

  await test.step("the planner closes the change and replays the run", async () => {
    await signOut(page);
    await signIn(page, "planner");
    await page.goto("/actions");
    await expect(page.getByText("R. Iyer")).toBeVisible();
    await page.getByRole("button", { name: "Close change" }).first().click();
    await page.getByRole("dialog").getByRole("button", { name: "Close change" }).click();
    await expect(page.getByRole("heading", { name: "Approved changes in progress" })).toHaveCount(0);
    await page.goto("/replay");
    await page.getByRole("button", { name: "Replay" }).first().click();
    await expect(page.getByText("The stored result was reproduced exactly.")).toBeVisible({ timeout: 60_000 });
  });

  await test.step("the audit history shows every step and survives a new session", async () => {
    await signOut(page);
    await signIn(page, "admin");
    await page.goto("/audit");
    await expect(page.getByText("Hash chain intact")).toBeVisible();
    for (const event of ["Document stored", "ECN received", "ECN confirmed", "Plan generated", "What if run", "Plan modified", "Plan approved", "Action status", "Change closed", "Run replayed"])
      await expect(page.getByRole("main").getByRole("button", { name: event }).first()).toBeVisible();
    await page.getByRole("button", { name: /Plan approved/ }).first().click();
    await expect(page.getByRole("dialog").getByText("supplier S1 agreed by phone", { exact: false })).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByLabel("Search events, people and references").fill("R. Iyer");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByRole("main").getByRole("button", { name: "Action assigned" })).toBeVisible();
    await page.goto("/dashboard");
    await expect(page.getByText("The change is closed")).toBeVisible();
  });
  expect(errors).toEqual([]);
});

test("missing and conflicting fields are corrected by a person", async ({ page }) => {
  await signIn(page, "engineering");
  await page.goto("/ecn");
  await page.getByRole("tab", { name: "Paste text" }).click();
  await page.getByLabel("Document text").fill([
    "Change ID: ECN-001", "Part number: MAT-101", "Old revision: B", "New revision: C", "Effective week: around W6 or W7",
    "Use-up end week: W5", "Interchangeable: Yes", "Reason: Improved mechanical durability", "Approval status: Approved"].join("\n"));
  await page.getByRole("button", { name: "Store and extract fields" }).click();
  await expect(page.getByText("Ambiguous", { exact: true })).toBeVisible();
  await expect(page.getByText("Missing", { exact: true })).toBeVisible();
  await page.getByLabel("I compared these fields with the document.").check();
  await expect(page.getByRole("button", { name: "Confirm the ECN" })).toBeDisabled();
  await page.getByLabel("Approver").fill("Engineering Manager");
  await page.getByLabel("Effective week").fill("7");
  await page.getByRole("button", { name: "Save corrections and validate" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /Record mismatch|Date conflict/ }).first()).toBeVisible();
  await page.getByLabel("Effective week").fill("6");
  await page.getByRole("button", { name: "Save corrections and validate" }).click();
  await expect(page.getByText("Corrected by hand").first()).toBeVisible();
  await page.getByRole("button", { name: "Confirm the ECN" }).click();
  await expect(page.getByRole("heading", { name: "Confirmed ECN" })).toBeVisible();
});

test("a document that cannot be read is refused and can be entered by hand", async ({ page }) => {
  await signIn(page, "engineering");
  await page.goto("/ecn");
  await page.locator("input[type=file]").setInputFiles({ name: "scan.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 broken") });
  await page.getByRole("button", { name: "Store and extract fields" }).click();
  await expect(page.getByText("The PDF could not be opened.").first()).toBeVisible();
  await page.getByRole("button", { name: "Enter fields by hand" }).first().click();
  await expect(page.getByText("No document, entered by hand")).toBeVisible();
  await page.goto("/ecn");
  await page.locator("input[type=file]").setInputFiles({ name: "fake.pdf", mimeType: "application/pdf", buffer: Buffer.from("not a pdf") });
  await page.getByRole("button", { name: "Store and extract fields" }).click();
  await expect(page.getByText("The file is not a PDF.")).toBeVisible();
});

test("no feasible plan: shortages, rejected plans, planner rejection", async ({ page }) => {
  await signIn(page, "planner");
  await selectVariant(page, "Blocked supplier");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("450 units of demand cannot be met");
  await expect(page.getByText("These are not the current records.")).toBeVisible();
  await page.goto("/ecn");
  await page.getByRole("tab", { name: "Sample" }).click();
  await page.getByLabel("Member 1 test document").selectOption("ECN-001");
  await page.getByRole("button", { name: "Store and extract fields" }).click();
  await page.getByLabel("I compared these fields with the document.").check();
  await page.getByRole("button", { name: "Confirm the ECN" }).click();
  await page.getByRole("button", { name: "Run the optimization" }).click();
  await expect(page).toHaveURL(/\/optimization/, { timeout: 60_000 });
  await expect(page.getByText("No feasible plan").first()).toBeVisible();
  await page.getByRole("tab", { name: "Rejected (7)" }).click();
  await expect(page.getByText(/Supplier S2 is blocked/).first()).toBeVisible();

  await page.goto("/exceptions");
  const first = page.getByRole("main").getByRole("listitem").filter({ hasText: "Production shortage" }).first();
  await expect(first).toContainText("Critical");
  await first.getByRole("button", { name: "Acknowledge" }).click();
  await expect(first.getByText("Acknowledged")).toBeVisible();
  await page.getByLabel("Severity", { exact: true }).selectOption({ label: "High" });
  await expect(page.getByRole("main").getByRole("listitem").filter({ hasText: "Production shortage" })).toHaveCount(0);
  await expect(page.getByRole("main").getByRole("listitem").filter({ hasText: "Rev B scrap risk" })).toBeVisible();
  await selectVariant(page, "Current records");
});

test("supplier delay: a plan is proposed, a planner rejects it", async ({ page }) => {
  await signIn(page, "planner");
  await selectVariant(page, "Rev C supplier delay");
  await page.goto("/ecn");
  await page.getByRole("tab", { name: "Sample" }).click();
  await page.getByLabel("Member 1 test document").selectOption("ECN-001");
  await page.getByRole("button", { name: "Store and extract fields" }).click();
  await page.getByLabel("I compared these fields with the document.").check();
  await page.getByRole("button", { name: "Confirm the ECN" }).click();
  await page.getByRole("button", { name: "Run the optimization" }).click();
  await expect(page.getByRole("article", { name: "Leading recommendation" }).getByText("Expedite PO-003 by 2 wk; Reduce PO-001 by 200")).toBeVisible({ timeout: 60_000 });
  await page.getByRole("link", { name: "Review and decide" }).click();
  await expect(page.getByRole("button", { name: "Reject" })).toBeDisabled();
  await page.getByLabel("Comment").fill("Expedite budget is not released.");
  await page.getByRole("button", { name: "Reject" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Reject" }).click();
  await expect(page.getByRole("heading", { name: "Rejected", exact: true })).toBeVisible();
  await selectVariant(page, "Current records");
});
