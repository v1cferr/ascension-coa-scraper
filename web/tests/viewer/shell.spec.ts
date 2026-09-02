import { expect, test, type Page } from "@playwright/test";

/**
 * The app shell owns the height: the window itself never scrolls, each pane scrolls
 * inside it, and the player is the bottom row.
 *
 * This is a regression guard. The shell used to let the navigator's list overflow its
 * own fixed-height column, which made the *document* scrollable — and the player, being
 * `sticky bottom-0` against the page root, rode that scroll up into the middle of the
 * screen instead of staying at the bottom.
 */

const documentScrolls = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollHeight > window.innerHeight + 1);

/** The player bar only mounts once something has sounds to play. */
async function openSubjectWithSound(page: Page) {
  await page.getByRole("button", { name: /^Templar/ }).click();
  await page.getByRole("button", { name: /^Class/ }).first().click();
  await page.getByRole("button", { name: /Testament of Hope/ }).first().click();
  const bar = page.locator("div.border-t").filter({ has: page.locator("audio") });
  await expect(bar).toBeVisible();
  return bar;
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByPlaceholder(/Filter classes, talents, spells/)).toBeVisible();
});

test("the window does not scroll, however long the navigator's list is", async ({ page }) => {
  expect(await documentScrolls(page)).toBe(false);
  // Expanding a class with 157 talents is what used to blow the column open.
  await page.getByRole("button", { name: /^Templar/ }).click();
  await page.getByRole("button", { name: /^Class/ }).first().click();
  await expect(page.getByRole("button", { name: /Testament of Hope/ }).first()).toBeVisible();
  expect(await documentScrolls(page)).toBe(false);
});

test("the navigator's list scrolls inside its column instead of overflowing it", async ({ page }) => {
  // The invariant `min-h-0` buys: a flex child defaults to min-height:auto, which lets it
  // grow to its content's full height. The column then clips it and the tail of the list
  // becomes unreachable — no scrollbar, because the box that scrolls is the one that grew.
  await page.getByRole("button", { name: /^Templar/ }).click();
  await page.getByRole("button", { name: /^Class/ }).first().click();
  await expect(page.getByRole("button", { name: /Testament of Hope/ }).first()).toBeVisible();

  const pane = page.locator('[data-slot="scroll-area"].flex-1').first();
  const viewport = page.viewportSize()!.height;
  const box = (await pane.boundingBox())!;
  expect(box.height).toBeLessThanOrEqual(viewport);

  // And the list really is scrollable, so those 157 talents stay reachable.
  const viewportEl = pane.locator('[data-slot="scroll-area-viewport"]');
  const overflow = await viewportEl.evaluate((el) => el.scrollHeight - el.clientHeight);
  expect(overflow).toBeGreaterThan(0);
});

test("the player stays on the bottom edge while the navigator is scrolled", async ({ page }) => {
  const bar = await openSubjectWithSound(page);
  const viewport = page.viewportSize()!.height;

  const settled = async () => (await bar.boundingBox())!;
  const before = await settled();
  expect(Math.round(before.y + before.height)).toBe(viewport);

  // The reported symptom: scrolling the left sidebar moved the player.
  await page.mouse.move(150, viewport / 2);
  await page.mouse.wheel(0, 1500);
  await page.waitForTimeout(400);

  const after = await settled();
  expect(Math.round(after.y + after.height)).toBe(viewport);
  expect(Math.round(after.y)).toBe(Math.round(before.y));
  expect(await documentScrolls(page)).toBe(false);
});

test("the player takes its own room rather than covering the panes", async ({ page }) => {
  const listPane = page.locator('[data-slot="scroll-area"].flex-1').first();
  const tallBefore = (await listPane.boundingBox())!.height;

  const bar = await openSubjectWithSound(page);
  const barBox = (await bar.boundingBox())!;
  const tallAfter = (await listPane.boundingBox())!.height;

  // The navigator yields exactly the player's height instead of running underneath it.
  expect(tallBefore - tallAfter).toBeCloseTo(barBox.height, 0);
});
