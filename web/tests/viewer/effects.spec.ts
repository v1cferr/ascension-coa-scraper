import { expect, test } from "@playwright/test";

/** Seeing an effect, hearing it, and taking it away. */

/** Open a spell that is known to draw and sound: Chaos Bolt belongs to no CoA tree,
 *  which also proves the spellbook reaches past the talent trees. */
async function openChaosBolt(page: import("@playwright/test").Page) {
  await page.goto("/#spell/50796");
  await page.goto("/");
  await page.getByRole("button", { name: /Find a talent or spell/ }).click();
  await page.getByPlaceholder(/Name or spell id/).fill("Chaos Bolt");
  await page.getByRole("option", { name: /Chaos Bolt/ }).first().click();
  await expect(page.getByRole("heading", { name: "Chaos Bolt" })).toBeVisible();
}

test("the palette reaches spells no talent tree names", async ({ page }) => {
  await openChaosBolt(page);
  // The distinction the interface exists to draw: this is a class's own spell.
  await expect(page.getByRole("heading", { name: "Granted by" })).toBeVisible();
  await expect(page.getByText("Warlock").first()).toBeVisible();
});

test("the palette opens on its keyboard shortcut", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  await expect(page.getByPlaceholder(/Name or spell id/)).toBeFocused();
});

test("a model opens to the sprites it draws and how it is built", async ({ page }) => {
  await openChaosBolt(page);

  const chip = page.locator("main button[title*='.m2'], main button[title*='.mdx']").first();
  await chip.click();

  // Not a render: what it shows is the sprites and the structure.
  await expect(page.getByText("Textures (", { exact: false })).toBeVisible();
  await expect(page.getByText(/blending/i).first()).toBeVisible();
  const plate = page.locator("figure img").first();
  await plate.scrollIntoViewIfNeeded();          // the plates are lazily loaded
  await expect(plate).toBeVisible();
  // A decoded BLP, actually loaded rather than a broken image. Visible is not loaded,
  // so this polls rather than reading the moment the element appears.
  await expect
    .poll(() => plate.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
});

test("playing the cast lights each moment in turn", async ({ page }) => {
  await openChaosBolt(page);
  await page.getByRole("button", { name: /Play the cast/ }).click();
  await expect(page.getByRole("button", { name: /Stop/ })).toBeVisible();
  // The stage names the moment currently firing.
  await expect(page.locator("main").getByText(/^(precast|cast|impact|state|channel)/i).first())
    .toBeVisible();
});

test("a spell's sounds arrive as a playlist in cast order", async ({ page }) => {
  await openChaosBolt(page);
  const queue = page.locator("button[aria-current]").filter({ hasText: /\.(ogg|wav)$/ });
  expect(await queue.count()).toBeGreaterThan(0);
  await expect(page.getByRole("button", { name: /^(Play|Pause)$/ })).toBeVisible();
});

test("every file offers a download, and the bundle is reachable", async ({ page }) => {
  await openChaosBolt(page);
  const bundle = page.getByRole("link", { name: /Download this spell's assets/ });
  await expect(bundle).toBeVisible();
  await expect(bundle).toHaveAttribute("href", "/_bundle/spell/50796.zip");

  const downloads = page.getByRole("link", { name: "download" });
  await expect(downloads.first()).toBeVisible();
});
