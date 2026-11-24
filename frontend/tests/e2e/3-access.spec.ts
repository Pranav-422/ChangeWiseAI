import { expect, test, type Page } from "@playwright/test";
import { collectErrors, email, signIn, signOut } from "./support";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";

async function tokenOf(page: Page) {
  const cookies = await page.context().cookies();
  const parts = cookies.filter((c) => /^sb-.*-auth-token(\.\d+)?$/.test(c.name)).sort((a, b) => a.name.localeCompare(b.name));
  const raw = decodeURIComponent(parts.map((c) => c.value).join(""));
  const json = raw.startsWith("base64-") ? Buffer.from(raw.slice(7), "base64url").toString() : raw;
  return JSON.parse(json).access_token as string;
}

test("calling the API by hand does not get around the role", async ({ page, request }) => {
  await signIn(page, "viewer");
  const headers = { Authorization: `Bearer ${await tokenOf(page)}` };
  expect((await request.get(`${API}/api/v1/auth/me`, { headers })).status()).toBe(200);
  for (const [path, body] of [
    ["/ecn/manual", { change_id: "ECN-001" }], ["/planning/optimize", { review_id: "x" }], ["/changes/ECN-001/simulate", undefined],
    ["/approvals/x/decision", { decision: "APPROVED", plan_id: "x" }], ["/audit/replay", { run_id: "x" }],
  ] as const) expect((await request.post(`${API}/api/v1${path}`, { headers, data: body })).status(), path).toBe(403);
  const me = await (await request.get(`${API}/api/v1/auth/me`, { headers })).json();
  expect((await request.patch(`${API}/api/v1/admin/users/${me.user_id}`, { headers, data: { role: "ADMIN" } })).status()).toBe(403);
  expect((await request.get(`${API}/api/v1/audit`)).status()).toBe(401);
  expect((await request.get(`${API}/api/v1/ecn`, { headers })).status()).toBe(403);
});

test("an administrator gives a role and takes access away", async ({ page, browser }) => {
  const address = `granted-${Date.now()}@changewise.test`;
  const other = await (await browser.newContext()).newPage();
  await other.goto("/signup");
  await other.getByLabel("Full name").fill("Granted Person");
  await other.getByLabel("Work email").fill(address);
  await other.getByLabel("Password").fill("a-long-password-1");
  await other.getByRole("button", { name: "Create account" }).click();
  await expect(other).toHaveURL(/\/dashboard$/);

  await signIn(page, "admin");
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Access" }).click();
  await page.getByLabel(`Role of ${address}`).selectOption({ label: "Production planner" });
  await expect(page.getByLabel(`Role of ${address}`)).toHaveValue("PRODUCTION_PLANNER");
  await expect(page.getByLabel(`Role of ${email("admin")}`)).toBeDisabled();
  await other.goto("/inventory");
  await expect(other.getByRole("button", { name: "Run and store simulation" })).toBeVisible();
  await page.getByRole("row", { name: new RegExp(address) }).getByRole("button", { name: "Remove access" }).click();
  await expect(page.getByRole("row", { name: new RegExp(address) }).getByText("No access")).toBeVisible();
  await other.goto("/inventory");
  await expect(other.getByText("This account has no access.")).toBeVisible();
});

test("no secret is in the browser bundle", async ({ page }) => {
  const scripts: string[] = [];
  page.on("response", async (r) => {
    if (r.url().includes("/_next/") && r.url().endsWith(".js")) scripts.push(await r.text().catch(() => ""));
  });
  await signIn(page, "planner");
  await page.goto("/optimization");
  const all = scripts.join("\n");
  expect(all.length).toBeGreaterThan(10_000);
  // the prefix alone is in supabase-js; a key is the prefix and its value. A boolean keeps the bundle out of the report.
  for (const secret of [/sb_secret_\w/, /service_role/, /GEMINI_API_KEY/, /postgres(ql)?:\/\//, /DATABASE_URL/])
    expect(secret.test(all), String(secret)).toBe(false);
});

test("backend failures are shown, not hidden", async ({ page }) => {
  await signIn(page, "planner");
  await page.route("**/api/v1/changes/*/overview*", (route) => route.fulfill({ status: 503, headers: { "access-control-allow-origin": "*" }, json: { error: { code: "DATABASE_UNAVAILABLE", message: "The database cannot be reached. Try again shortly.", details: [], request_id: "r1" } } }));
  await page.goto("/dashboard");
  await expect(page.getByText("The database cannot be reached.")).toBeVisible();
  await page.unroute("**/api/v1/changes/*/overview*");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

const PAGES = ["dashboard", "engineering-changes", "engineering-changes/ECN-001", "ecn", "bom", "inventory", "optimization", "what-if", "exceptions", "approvals", "actions", "audit", "replay", "settings"];

for (const [name, width, height] of [["desktop", 1440, 900], ["laptop", 1180, 760], ["tablet", 820, 1100], ["mobile", 390, 844]] as const) {
  test(`every page fits ${name}`, async ({ page }) => {
    test.setTimeout(180_000);
    const errors = collectErrors(page);
    await page.setViewportSize({ width, height });
    await signIn(page, "planner");
    for (const path of PAGES) {
      await page.goto(`/${path}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `${path} at ${width}`).toBeLessThanOrEqual(0);
    }
    expect(errors).toEqual([]);
  });
}

test("keyboard: skip link, navigation, quick jump, tabs, chart weeks", async ({ page }) => {
  await signIn(page, "planner");
  await page.goto("/inventory");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#content")).toBeFocused();
  await page.getByRole("button", { name: /^Week 3:/ }).focus();
  await expect(page.getByRole("status").filter({ hasText: "W3" })).toContainText("Demand");
  await page.getByRole("tab", { name: "Rev B" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Rev C" })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Control+k");
  await page.getByLabel("Page or change").fill("exception");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/exceptions$/);
});

test("mobile navigation opens and closes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "planner");
  await expect(page.getByRole("navigation", { name: "Main" })).not.toBeInViewport();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Inventory monitor" }).click();
  await expect(page).toHaveURL(/\/inventory$/);
  await signOut(page);
});
