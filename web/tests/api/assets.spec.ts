import { expect, test } from "@playwright/test";

/** The derived routes: what a model is made of, and its textures as something a
 *  browser can show. */

test("a model reports its structure and its textures", async ({ request }) => {
  const info = await (await request.get("/_model/SPELLS/leishen_lightning_column.m2")).json();

  expect(info.name).toBe("LeiShen_Lightning_Column");
  expect(info.counts.particle_emitters).toBeGreaterThan(0);
  expect(info.textures.length).toBeGreaterThan(0);
  // Additive blending is what makes an effect read as light rather than paint.
  expect(info.glows).toBe(true);
  for (const emitter of info.emitters) {
    expect(emitter.blend).not.toMatch(/^mode \d+$/);   // a name, not a raw byte
    expect(emitter.kind).not.toMatch(/^type \d+$/);
  }
});

test("a model named .mdx is found as the .m2 on disk", async ({ request }) => {
  // A tenth of the dataset's model references use the Warcraft III extension for
  // files stored as M2. The client makes this swap; so must the route.
  const response = await request.get("/_model/Spells/Fire_Cast_Hand.mdx");
  expect(response.status()).toBe(200);
});

test("a texture comes back as a PNG the browser can render", async ({ request }) => {
  const response = await request.get("/_texture/spells/star6.blp");

  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("image/png");
  const body = await response.body();
  expect(body.subarray(0, 8)).toEqual(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
});

test("present but undecodable is answered differently from missing", async ({ request }) => {
  // One texture in this client uses a BLP alpha encoding the decoder does not
  // implement. Answering 404 would send a reader to re-run an extraction that worked.
  const undecodable = await request.get(
    "/_texture/world/expansion08/doodads/fx/9fx_generic_anima_revendreth_buff_3183248.blp",
  );
  expect(undecodable.status()).toBe(415);
  expect((await request.get("/_texture/spells/definitely-not-here.blp")).status()).toBe(404);
});

test("asset paths cannot escape the archive", async ({ request }) => {
  for (const attack of ["/_texture/../../../etc/passwd", "/_texture/..%2f..%2fREADME.md"]) {
    expect((await request.get(attack)).status()).toBe(404);
  }
});

test("a bundle is a real zip carrying more than the dataset names", async ({ request }) => {
  const response = await request.get("/_bundle/spell/50796.zip");

  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("application/zip");
  expect(response.headers()["content-disposition"]).toContain("attachment");

  const body = await response.body();
  expect(body.subarray(0, 2)).toEqual(Buffer.from("PK"));

  // A model alone opens to nothing, so each brings its .skin geometry and textures:
  // the bundle holds more files than the spell's own model and sound list.
  const record = await (await request.get("/_spell/50796")).json();
  const named = record.effects.models.length + record.effects.sounds.length;
  expect(Number(response.headers()["x-bundle-files"])).toBeGreaterThan(named);
});
