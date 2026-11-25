import { expect, type Page } from "@playwright/test";

// Test accounts of the local stack (scripts/dev) or of the CI Supabase project (scripts/dev/seed_supabase.py).
export const PASSWORD = process.env.E2E_PASSWORD ?? "local-test-password";
export const email = (name: string) => `${name}@changewise.test`;

export async function signIn(page: Page, name: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Work email").fill(email(name));
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

export async function signOut(page: Page) {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Sign out" }).last().click();
  await expect(page).toHaveURL(/\/login/);
}

export async function selectVariant(page: Page, name: string) {
  await page.getByLabel("Data variant").selectOption({ label: name });
}

export function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => {
    // a refused request is logged by the browser itself; the tests assert those separately
    if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) errors.push(m.text());
  });
  return errors;
}
