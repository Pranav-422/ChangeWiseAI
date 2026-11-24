import { expect, test } from "@playwright/test";
import { signOut } from "./support";

test.skip(!process.env.E2E_REAL_SUPABASE, "needs the real Supabase stack (CI)");

test("password reset through the delivered e-mail", async ({ page, request }) => {
  const address = `mail-${Date.now()}@changewise.test`;
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Mail Person");
  await page.getByLabel("Work email").fill(address);
  await page.getByLabel("Password").fill("first-password-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await signOut(page);
  await page.goto("/reset-password");
  await page.getByLabel("Work email").fill(address);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByText("Request received")).toBeVisible();

  const mail = process.env.E2E_MAIL_URL ?? "http://127.0.0.1:54324";
  let link = "";
  await expect(async () => {
    const found = await (await request.get(`${mail}/api/v1/search?query=to:${address}`)).json();
    const message = await (await request.get(`${mail}/api/v1/message/${found.messages[0].ID}`)).json();
    link = /href="([^"]+verify[^"]+)"/.exec(message.HTML)![1]!.replaceAll("&amp;", "&");
  }).toPass({ timeout: 20_000 });
  await page.goto(link);
  await expect(page).toHaveURL(/\/update-password$/);
  await page.getByLabel("New password").fill("second-password-2");
  await page.getByLabel("Repeat the password").fill("second-password-2");
  await page.getByRole("button", { name: "Save password" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});
