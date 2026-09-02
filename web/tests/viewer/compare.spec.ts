import { expect, test, type Page } from "@playwright/test";

/**
 * The compare board. It exists because comparing is what two people designing a mod
 * do, and each card must keep the accent it was pinned with — otherwise putting two
 * classes side by side shows one colour twice.
 */

const nav = (page: Page) => page.getByRole("navigation", { name: "View" });
const filter = (page: Page) => page.getByPlaceholder(/Filter classes, talents, spells/);
const cards = (page: Page) => page.locator("main article");

async function pinSpell(page: Page, query: string, name: RegExp) {
  await filter(page).fill(query);
  const row = page.getByRole("button", { name }).first();
  await expect(row).toBeVisible();
  await page.getByRole("button", { name: new RegExp(`Pin .*${name.source}`, "i") }).first().click();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(filter(page)).toBeVisible();
});

test("the board starts empty and says how to fill it", async ({ page }) => {
  await nav(page).getByRole("tab", { name: "Compare" }).click();
  await expect(page.getByText("0 pinned")).toBeVisible();
  await expect(page.getByText(/Pin a talent or spell/)).toBeVisible();
  await expect(cards(page)).toHaveCount(0);
});

test("pinning from the navigator puts a card on the board", async ({ page }) => {
  await pinSpell(page, "chaos bolt", /Chaos Bolt/);
  await expect(nav(page).getByRole("tab", { name: /Compare/ })).toContainText("1");

  await nav(page).getByRole("tab", { name: /Compare/ }).click();
  await expect(cards(page)).toHaveCount(1);
  const card = cards(page).first();
  await expect(card.getByRole("heading", { name: "Chaos Bolt" })).toBeVisible();
  // The card is self-contained: its own score and its own sounds.
  await expect(card.getByText(/cast|impact|precast/i).first()).toBeVisible();
});

/** Pin a named talent from a named class and tree.
 *
 *  Named rather than "whatever is first": reading a name out of the list and then
 *  clicking its pin races the list itself, which swaps as the next tree lands, and the
 *  button detaches between the read and the click. */
async function pinTalent(page: Page, cls: RegExp, tree: RegExp, talent: string) {
  await page.getByRole("button", { name: cls }).click();
  const treeRow = page.getByRole("button", { name: tree });
  await treeRow.click();
  await expect(treeRow).toHaveAttribute("aria-expanded", "true");
  const pin = page.getByRole("button", { name: `Pin ${talent} to the board` });
  await expect(pin).toBeVisible();
  await pin.click();
}

test("each card keeps the accent it was pinned with", async ({ page }) => {
  // Two classes whose dataset colours differ.
  await pinTalent(page, /^Stormbringer/, /^Lightning\s+\d+$/, "Arm of Thorim");
  await pinTalent(page, /^Pyromancer/, /^Incineration\s+\d+$/, "Ignite");

  await nav(page).getByRole("tab", { name: /Compare/ }).click();
  await expect(cards(page)).toHaveCount(2);

  const accents = await cards(page).evaluateAll((nodes) =>
    nodes.map((n) => getComputedStyle(n).getPropertyValue("--class").trim()));
  expect(new Set(accents).size).toBe(2);
});

test("pinning the same subject again takes it off the board", async ({ page }) => {
  await pinSpell(page, "chaos bolt", /Chaos Bolt/);
  await expect(nav(page).getByRole("tab", { name: /Compare/ })).toContainText("1");
  await page.getByRole("button", { name: /Chaos Bolt is on the board/i }).click();
  await nav(page).getByRole("tab", { name: "Compare" }).click();
  await expect(cards(page)).toHaveCount(0);
});

test("a card can be removed, and the board cleared", async ({ page }) => {
  await pinSpell(page, "chaos bolt", /Chaos Bolt/);
  await nav(page).getByRole("tab", { name: /Compare/ }).click();
  await cards(page).first().getByRole("button", { name: /Remove Chaos Bolt/ }).click();
  await expect(cards(page)).toHaveCount(0);

  await pinSpell(page, "ice block", /Ice Block/);
  await nav(page).getByRole("tab", { name: /Compare/ }).click();
  await expect(cards(page)).toHaveCount(1);
  await page.getByRole("button", { name: "Clear all" }).click();
  await expect(cards(page)).toHaveCount(0);
});

test("the reader can pin what it is showing", async ({ page }) => {
  await filter(page).fill("chaos bolt");
  await page.getByRole("button", { name: /Chaos Bolt/ }).first().click();
  const pin = page.getByRole("button", { name: /Pin to compare/ });
  await pin.click();
  await expect(page.getByRole("button", { name: /On the board/ })).toBeVisible();
  await nav(page).getByRole("tab", { name: /Compare/ }).click();
  await expect(cards(page)).toHaveCount(1);
});
