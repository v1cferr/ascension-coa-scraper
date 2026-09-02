import { test, type Page } from "@playwright/test";

/** Not an assertion — a way to capture the board with two cards from different classes
 *  for visual review. Skipped unless SHOT is set. */
test.skip(!process.env.SHOT, "capture only");

async function pinFrom(page: Page, cls: RegExp, tree: RegExp) {
  await page.getByRole("button", { name: cls }).click();
  await page.getByRole("button", { name: tree }).first().click();
  const row = page.locator("button[aria-current]").filter({ hasText: /\d{4,}/ }).first();
  const name = (await row.textContent())?.replace(/\d+\s*$/, "").trim() ?? "";
  await page.getByRole("button", { name: new RegExp(`Pin ${name}`, "i") }).click();
}

test("board with two accents", async ({ page }) => {
  await page.setViewportSize({ width: 1700, height: 1200 });
  await page.goto("/");
  await pinFrom(page, /^Stormbringer/, /^Lightning/);
  await pinFrom(page, /^Pyromancer/, /^\w+\s+\d+$/);
  await page.getByRole("navigation", { name: "View" }).getByRole("tab", { name: /Compare/ }).click();
  await page.waitForTimeout(2500);          // let the sprite thumbnails decode
  await page.screenshot({ path: process.env.SHOT!, fullPage: false });
});
