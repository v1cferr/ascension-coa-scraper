import { expect, test, type Page } from "@playwright/test";

/** Navigating the archive: the navigator, the three views, and reading one subject. */

const nav = (page: Page) => page.getByRole("navigation", { name: "View" });
const filter = (page: Page) => page.getByPlaceholder(/Filter classes, talents, spells/);

/** Open a class, then its first tree, so its talents are listed. */
async function openFirstTree(page: Page) {
  const stormbringer = page.getByRole("button", { name: /^Stormbringer/ });
  await stormbringer.click();
  await expect(stormbringer).toHaveAttribute("aria-expanded", "true");
  const tree = page.getByRole("button", { name: /^Lightning/ }).first();
  await tree.click();
  await expect(tree).toHaveAttribute("aria-expanded", "true");
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(filter(page)).toBeVisible();
});

test("opens on the subject view, asking for a subject", async ({ page }) => {
  await expect(nav(page).getByRole("tab", { name: "Subject" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Pick a talent or a spell")).toBeVisible();
});

test("the navigator drills from class to tree to talent", async ({ page }) => {
  await openFirstTree(page);
  // Talent rows carry the spell id, which is how you tell them from tree rows.
  const talents = page.locator("button[aria-current]").filter({ hasText: /\d{4,}/ });
  expect(await talents.count()).toBeGreaterThan(5);
});

test("the filter narrows classes and talents together", async ({ page }) => {
  await openFirstTree(page);
  const before = await page.locator("button[aria-current]").count();
  await filter(page).fill("storm");
  await expect(page.getByRole("button", { name: /^Stormbringer/ })).toBeVisible();
  // Barbarian does not match, so it goes.
  await expect(page.getByRole("button", { name: /^Barbarian/ })).toHaveCount(0);
  expect(await page.locator("button[aria-current]").count()).toBeLessThan(before);
});

test("choosing a talent fills the reader", async ({ page }) => {
  await openFirstTree(page);
  const talent = page.locator("button[aria-current]").filter({ hasText: /\d{4,}/ }).first();
  const name = (await talent.textContent())?.replace(/\d+\s*$/, "").trim() ?? "";
  await talent.click();
  await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  await expect(page.getByRole("button", { name: /Pin to compare/ })).toBeVisible();
});

test("the tree view draws the tree", async ({ page }) => {
  await nav(page).getByRole("tab", { name: "Tree" }).click();
  const nodes = page.locator("main button[aria-pressed]");
  await expect(nodes.first()).toBeVisible();
  expect(await nodes.count()).toBeGreaterThan(10);
});

test("the class colour follows the class that is chosen", async ({ page }) => {
  const colour = () => page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--class").trim());

  const before = await colour();
  await page.getByRole("button", { name: /^Venomancer/ }).click();
  await expect(async () => expect(await colour()).not.toBe(before)).toPass();
});

test("a spell the trees do not name is reachable from the navigator", async ({ page }) => {
  await filter(page).fill("chaos bolt");
  const hit = page.getByRole("button", { name: /Chaos Bolt/ }).first();
  await expect(hit).toBeVisible();
  await hit.click();
  await expect(page.getByRole("heading", { level: 2, name: "Chaos Bolt" })).toBeVisible();
  // The distinction the interface exists to draw.
  await expect(page.getByRole("heading", { name: "Granted by" })).toBeVisible();
  await expect(page.getByText("Warlock").first()).toBeVisible();
});
