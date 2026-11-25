import { expect, test } from "@playwright/test";
import { PASSWORD, email, signIn, signOut } from "./support";

test("protected pages send a visitor to sign in and back", async ({ page }) => {
  for (const path of ["/dashboard", "/ecn", "/approvals", "/audit", "/settings", "/update-password"]) {
    await page.goto(path);
    await expect(page).toHaveURL(new RegExp(`/login\\?next=${encodeURIComponent(path)}`));
  }
  await page.goto("/inventory");
  await page.getByLabel("Work email").fill(email("viewer"));
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/inventory$/);
});

test("a wrong password is refused and an outside return address is ignored", async ({ page }) => {
  await page.goto("/login?next=//evil.example/x");
  await page.getByLabel("Work email").fill(email("viewer"));
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("The email or password is not correct.")).toBeVisible();
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/localhost:\d+\/dashboard$/);
});

test("session survives a reload and ends with sign out", async ({ page }) => {
  await signIn(page, "viewer");
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await signOut(page);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

test("a new account starts as a viewer, whatever it sends", async ({ page }) => {
  const address = `new-${Date.now()}@changewise.test`;
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("New Person");
  await page.getByLabel("Work email").fill(address);
  await page.getByLabel("Password").fill("a-long-password-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/settings");
  await expect(page.getByRole("main").getByText("Viewer", { exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Access" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Audit history" })).toHaveCount(0);
});

test("a guest enters without an account and only views", async ({ page }) => {
  await page.goto("/login?next=/inventory");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await expect(page).toHaveURL(/:\d+\/inventory$/);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.goto("/settings");
  await expect(page.getByRole("main").getByText("Viewer", { exact: true })).toBeVisible();
  await expect(page.getByText("None, guest session")).toBeVisible();
  await expect(page.getByRole("link", { name: "Change password" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Audit history" })).toHaveCount(0);
  await signOut(page);
});

test("password reset by e-mail link", async ({ page, request }) => {
  test.skip(!!process.env.E2E_REAL_SUPABASE, "the real stack delivers the link by mail; see 5-real-supabase.spec.ts");
  const address = `reset-${Date.now()}@changewise.test`;
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Reset Person");
  await page.getByLabel("Work email").fill(address);
  await page.getByLabel("Password").fill("first-password-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await signOut(page);
  await page.getByRole("link", { name: "Forgot your password?" }).click();
  await page.getByLabel("Work email").fill(address);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByText("Request received")).toBeVisible();
  const { token_hash } = await (await request.get(`http://localhost:54321/dev/recovery-token?email=${address}`)).json();
  await page.goto(`/auth/confirm?token_hash=${token_hash}&type=recovery`);
  await expect(page).toHaveURL(/\/update-password$/);
  await page.getByLabel("New password").fill("second-password-2");
  await page.getByLabel("Repeat the password").fill("second-password-2");
  await page.getByRole("button", { name: "Save password" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await signOut(page);
  await page.getByLabel("Work email").fill(address);
  await page.getByLabel("Password").fill("second-password-2");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto(`/auth/confirm?token_hash=${token_hash}&type=recovery`);
  await expect(page).toHaveURL(/reason=link/); // a link works once
});

test("an expired session leads to sign in with a reason", async ({ page }) => {
  await signIn(page, "viewer");
  await page.route("**/api/v1/**", (route) => route.fulfill({ status: 401, headers: { "access-control-allow-origin": "*" }, json: { error: { code: "UNAUTHENTICATED", message: "Sign in again.", details: [] } } }));
  await page.goto("/exceptions");
  await expect(page).toHaveURL(/reason=expired/);
  await expect(page.getByText("Your session ended.")).toBeVisible();
});
