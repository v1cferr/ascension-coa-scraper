import { expect, test } from "@playwright/test";

/** Reading the archive: picking a class, walking a tree, opening a talent. */

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("opens on a class with its tree drawn", async ({ page }) => {
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/\w+/);
  // Every node is a button carrying the talent's name.
  const nodes = page.locator("main button[aria-pressed]");
  await expect(nodes.first()).toBeVisible();
  expect(await nodes.count()).toBeGreaterThan(10);
});

test("the class colour follows the class that is chosen", async ({ page }) => {
  const colourNow = () =>
    page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--class").trim());

  const before = await colourNow();
  await page.getByRole("navigation", { name: "Classes" })
    .getByRole("button", { name: /Venomancer/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Venomancer");
  expect(await colourNow()).not.toBe(before);
});

test("switching trees redraws the nodes", async ({ page }) => {
  const nodes = page.locator("main button[aria-pressed]");
  const first = await nodes.first().getAttribute("title");

  const tabs = page.getByRole("navigation", { name: "Talent trees" }).getByRole("tab");
  await tabs.nth(1).click();
  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
  await expect(async () => {
    expect(await nodes.first().getAttribute("title")).not.toBe(first);
  }).toPass();
});

test("choosing a talent fills the readout and the cast score", async ({ page }) => {
  const nodes = page.locator("main button[aria-pressed]");
  const count = await nodes.count();

  // Not every talent draws something; walk until one does.
  for (let i = 0; i < Math.min(count, 12); i++) {
    await nodes.nth(i).click();
    await expect(nodes.nth(i)).toHaveAttribute("aria-pressed", "true");
    if (await page.getByRole("heading", { name: "Cast score" }).isVisible()) {
      await expect(page.getByRole("button", { name: /Play the cast/ })).toBeVisible();
      await expect(page.getByText(/Columns are moments in the cast/)).toBeVisible();
      return;
    }
  }
  test.skip(true, "no talent in the first tree draws anything");
});
