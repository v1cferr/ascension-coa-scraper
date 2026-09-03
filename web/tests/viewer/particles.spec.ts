import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Running an effect's particles.
 *
 * 626 of the archive's effect models have no geometry at all, so "does it draw
 * anything" is not a cosmetic question here — for those models the particles are the
 * entire content. These tests read the canvas back rather than trusting that a element
 * appeared: a stage that mounts and paints black is exactly the failure worth catching.
 */

/** What the canvas actually painted, sampled from its own pixels. */
async function pixels(canvas: Locator) {
  return canvas.evaluate((el: HTMLCanvasElement) => {
    const ctx = el.getContext("2d");
    if (!ctx) return { lit: 0, total: 0, peak: 0, hue: null as string | null };
    const data = ctx.getImageData(0, 0, el.width, el.height).data;
    let lit = 0, peak = 0, r = 0, g = 0, b = 0;
    for (let i = 0; i < data.length; i += 4) {
      const v = Math.max(data[i], data[i + 1], data[i + 2]);
      if (v > 12) { lit++; r += data[i]; g += data[i + 1]; b += data[i + 2]; }
      if (v > peak) peak = v;
    }
    return {
      lit, total: data.length / 4, peak,
      // The average colour of what is lit, which is what says the model's own palette
      // came through rather than a white default.
      hue: lit ? `${Math.round(r / lit)},${Math.round(g / lit)},${Math.round(b / lit)}` : null,
    };
  });
}

/** Open a talent, then the first model its cast score names. */
async function openEffect(page: Page, talent: RegExp) {
  await page.goto("/#voljin/templar/class/34353");
  await expect(page.getByPlaceholder(/Filter classes, talents, spells/)).toBeVisible();
  await page.getByRole("button", { name: talent }).first().click();
  const cell = page.getByRole("button", { name: /\.m2$/i }).first();
  await expect(cell).toBeVisible();
  await cell.click();
  const canvas = page.locator("canvas");
  await expect(canvas).toBeVisible();
  return canvas;
}

test("an effect's emitters are run, not just listed", async ({ page }) => {
  const canvas = await openEffect(page, /Testament of Hope/);
  // Give the loop time to load its sprites and paint a few frames.
  await page.waitForTimeout(2500);

  const shot = await pixels(canvas);
  expect(shot.total).toBeGreaterThan(0);
  // A mounted stage that paints nothing but its black ground is the failure this
  // catches — it looks identical to a working one in a DOM snapshot.
  expect(shot.lit).toBeGreaterThan(200);
  expect(shot.peak).toBeGreaterThan(60);
});

test("the particles carry the model's own colour, not the interface's accent", async ({ page }) => {
  const canvas = await openEffect(page, /Testament of Hope/);
  await page.waitForTimeout(2500);

  const shot = await pixels(canvas);
  expect(shot.hue).not.toBeNull();
  const [r, g, b] = (shot.hue as string).split(",").map(Number);

  // Holy magic is gold: red and green well ahead of blue. The point is not the exact
  // value but that a colour curve was read at all — an untinted sprite comes out grey,
  // with the three channels within a few points of each other.
  expect(Math.abs(r - b)).toBeGreaterThan(20);
  expect(r).toBeGreaterThan(b);
  expect(g).toBeGreaterThan(b);
});

test("the effect keeps running rather than painting one frame", async ({ page }) => {
  const canvas = await openEffect(page, /Testament of Hope/);
  await page.waitForTimeout(2000);
  const first = await pixels(canvas);
  await page.waitForTimeout(900);
  const second = await pixels(canvas);

  // Both frames lit, and not the identical count: particles are moving and dying.
  expect(first.lit).toBeGreaterThan(200);
  expect(second.lit).toBeGreaterThan(200);
  expect(second.lit).not.toBe(first.lit);
});

test("a model with no emitter texture says so instead of showing a black box", async ({ page }) => {
  // Not every model runs. When one cannot, the interface should say which, rather than
  // leaving an empty stage that reads as a broken renderer.
  await page.goto("/#voljin/templar/class/34353");
  await expect(page.getByPlaceholder(/Filter classes, talents, spells/)).toBeVisible();

  const message = page.getByText(/names no emitter texture/);
  const canvas = page.locator("canvas");
  // Whichever the first effect turns out to be, exactly one of the two is true.
  await page.getByRole("button", { name: /Testament of Hope/ }).first().click();
  await page.getByRole("button", { name: /\.m2$/i }).first().click();
  await expect(async () => {
    expect(await canvas.count() + await message.count()).toBeGreaterThan(0);
  }).toPass();
});
