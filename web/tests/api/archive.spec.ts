import { expect, test } from "@playwright/test";

/**
 * The dataset the viewer reads. These assert on shape and on invariants that hold
 * whatever the archive currently contains — counts change every time the client is
 * re-extracted, so pinning them would make the suite fail on success.
 */

test("the index names realms, classes and where the assets live", async ({ request }) => {
  const index = await (await request.get("/data/index.json")).json();

  expect(index.schema_version).toBe(1);
  expect(index.asset_root).toBeTruthy();
  expect(index.realms.length).toBeGreaterThan(0);

  for (const realm of index.realms) {
    expect(realm.slug).toMatch(/^[a-z0-9-]+$/);
    expect(realm.classes.length).toBeGreaterThan(0);
    for (const cls of realm.classes) {
      // The colour is the one thing the whole interface is themed from.
      expect(cls.color).toMatch(/^rgb\(\s*\d+,\s*\d+,\s*\d+\s*\)$/);
      expect(cls.trees.length).toBeGreaterThan(0);
      expect(cls.talent_count).toBeGreaterThan(0);
    }
  }
});

test("a tree's talents carry positions, costs and a graph", async ({ request }) => {
  const index = await (await request.get("/data/index.json")).json();
  const cls = index.realms[0].classes[0];
  const payload = await (await request.get(`/data/${cls.dir}/${cls.trees[0].file}`)).json();

  const talents = payload.tree.talents;
  expect(talents.length).toBe(cls.trees[0].talent_count);

  const ids = new Set(talents.map((t: { id: number }) => t.id));
  for (const talent of talents) {
    expect(talent.position.x).toBeGreaterThanOrEqual(0);
    expect(talent.position.y).toBeGreaterThanOrEqual(0);
    expect(["circle", "square", "hex"]).toContain(talent.node_shape);
    expect(["talent", "ability"]).toContain(talent.entry_type);
    expect(talent.max_ranks).toBeGreaterThanOrEqual(1);
    // Upstream pads these arrays with zeroes; the scraper strips them, so every
    // connection left should point at a talent that exists in the same tree.
    for (const other of talent.connections) expect(ids).toContain(other);
  }
});

test("search finds a spell by name and ranks the class's own first", async ({ request }) => {
  const body = await (await request.get("/_spells?q=Blizzard&limit=5")).json();
  expect(body.results.length).toBeGreaterThan(0);

  const top = body.results[0];
  expect(top.name).toBe("Blizzard");
  // Dozens of rows share this name; the one worth showing is the one a class grants.
  expect(top.owners.length).toBeGreaterThan(0);
  expect(top.owners[0].class).toBe("Mage");
});

test("search treats LIKE wildcards as literal text", async ({ request }) => {
  // Unescaped, "%" would match every row in the table.
  const body = await (await request.get("/_spells?q=%25&limit=5")).json();
  for (const hit of body.results) expect(hit.name).toContain("%");
});

test("a spell resolves to its cast, and says who grants it", async ({ request }) => {
  const record = await (await request.get("/_spell/50796")).json();

  expect(record.name).toBe("Chaos Bolt");
  expect(record.owners.some((o: { class: string }) => o.class === "Warlock")).toBe(true);

  const kits = record.effects.kits;
  expect(kits.length).toBeGreaterThan(0);
  for (const kit of kits) {
    // A kit with neither a model nor a sound would be padding, and is dropped.
    expect(Object.keys(kit.models).length + (kit.sound ? 1 : 0)).toBeGreaterThan(0);
  }
});

test("a spell the client does not have is a 404, not an empty answer", async ({ request }) => {
  expect((await request.get("/_spell/999999999")).status()).toBe(404);
});
