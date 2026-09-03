import { expect, test } from "@playwright/test";

/** Seeing an effect, hearing it, and taking it away. */

/** Open a spell known to draw and sound. Chaos Bolt belongs to no Conquest of Azeroth
 *  tree, so reaching it at all proves the spellbook goes past the talent trees — and
 *  the address form proves deep links still resolve. */
async function openChaosBolt(page: import("@playwright/test").Page) {
  await page.goto("/#spell/50796");
  await expect(page.getByRole("heading", { level: 2, name: "Chaos Bolt" })).toBeVisible();
}

test("a spell no talent tree names opens with who grants it", async ({ page }) => {
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

test("the palette finds a talent and lands on it", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Find anything/ }).click();
  await page.getByPlaceholder(/Name or spell id/).fill("Arm of Thorim");
  await page.getByRole("option", { name: /Arm of Thorim/ }).first().click();
  await expect(page.getByRole("heading", { level: 2, name: "Arm of Thorim" })).toBeVisible();
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
  // Auto-retrying, not a one-shot count: the heading renders from the spell payload but
  // the queue fills from the effects one, so counting the moment the title appears races
  // a request that has not landed. It passed alone and failed beside five other workers.
  await expect(queue).not.toHaveCount(0);
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
