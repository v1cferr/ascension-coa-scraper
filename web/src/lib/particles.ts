/**
 * Running a spell's particle emitters.
 *
 * 626 of the archive's 1,486 effect models have no geometry at all — they are emitters
 * and nothing else. Showing their textures as stills says what an effect is made of but
 * not what it looks like, because for these models the motion *is* the effect.
 *
 * The numbers driving this come from the client's own files: speed, gravity, lifespan,
 * emission rate, and the colour, alpha and size curves across one particle's life. What
 * is simulated here is only what the data actually carries. Where the reader could not
 * resolve a track it sends null, and null is treated as "this emitter does not do that"
 * rather than filled in with a plausible number — a made-up gravity is indistinguishable
 * from a real one once it is moving.
 */

import type { ParticleEmitter } from "@/lib/types";

/** Colour channels arrive 0..255 from the model. */
const CHANNEL = 255;

/** Emitters can ask for more than a canvas can draw; this caps the cost, not the look. */
const MAX_PARTICLES = 1200;

/** A stand-in lifespan for an emitter whose track did not resolve, so it still shows. */
const FALLBACK_LIFESPAN = 0.8;

export type Particle = {
  x: number; y: number;
  vx: number; vy: number;
  age: number;
  life: number;
  tile: number;
};

/** Sample a curve of keys at `t` in 0..1, interpolating between the two around it. */
export function sample<T extends number | number[]>(
  keys: [number, T][], t: number, fallback: T,
): T {
  if (!keys.length) return fallback;
  if (t <= keys[0][0]) return keys[0][1];
  const last = keys[keys.length - 1];
  if (t >= last[0]) return last[1];

  let i = 0;
  while (i < keys.length - 1 && keys[i + 1][0] < t) i++;
  const [t0, a] = keys[i];
  const [t1, b] = keys[i + 1];
  const span = t1 - t0;
  const f = span > 0 ? (t - t0) / span : 0;

  if (typeof a === "number" && typeof b === "number") {
    return (a + (b - a) * f) as T;
  }
  const from = a as number[];
  const to = b as number[];
  return from.map((v, n) => v + ((to[n] ?? v) - v) * f) as T;
}

/** How many particles an emitter sustains: rate × life, which is its steady state. */
export function population(emitter: ParticleEmitter): number {
  const rate = emitter.emission_rate ?? 0;
  const life = emitter.lifespan ?? FALLBACK_LIFESPAN;
  return Math.min(MAX_PARTICLES, Math.ceil(Math.max(rate, 1) * Math.max(life, 0.05)));
}

/**
 * The world-to-pixel scale that fits this effect on a canvas.
 *
 * Model units are arbitrary and tiny — a typical spell throws particles at 0.5 units a
 * second and sizes them at 0.03. Rather than hardcode a number that suits one effect and
 * clips another, the reach is derived from how far a particle actually travels in its
 * lifetime, so every effect arrives framed.
 */
export function fitScale(
  emitters: ParticleEmitter[], pools: Particle[][], pixels: number,
): number {
  // Adding up the fields that *could* contribute overestimates badly: an emission area
  // spawns particles across it without any of them travelling that far, and the effect
  // ends up drawn at a fraction of the canvas. So the pools are measured instead. What
  // is scaled to fit is where the particles actually got to, which no field can lie
  // about.
  const radii: number[] = [];
  pools.forEach((pool, i) => {
    const emitter = emitters[i];
    if (!emitter) return;
    const size = emitter.scales.length
      ? Math.max(...emitter.scales.map(([, s]) => Math.max(s[0], s[1])))
      : 0.05;
    for (const p of pool) {
      // Weighted by whether the particle can actually be seen. A spray whose outliers
      // have already faded to nothing should not set the frame for the bright core
      // everyone is looking at.
      if (appearance(emitter, p).alpha < 0.08) continue;
      radii.push(Math.hypot(p.x, p.y) + size);
    }
  });
  if (!radii.length) return pixels;

  // The 65th percentile of what is visible. Higher, and one particle thrown far shrinks
  // the rest to a dot; lower, and the effect spills past the frame. Some clipping at the
  // edge is the better trade: an effect too small to read is worse than one cropped.
  radii.sort((a, b) => a - b);
  const reach = Math.max(0.02, radii[Math.floor(radii.length * 0.65)]);
  return (pixels * 0.5) / reach;
}

/** Step a copy of the pools far enough that the spread is representative. */
export function settle(
  emitters: ParticleEmitter[], pools: Particle[][], rand: () => number,
): void {
  for (let n = 0; n < 30; n++) {
    pools.forEach((pool, i) => step(pool, emitters[i], 1 / 60, rand));
  }
}

/** Give one particle a fresh birth, in place, so the pool never reallocates. */
export function spawn(p: Particle, emitter: ParticleEmitter, rand: () => number): void {
  const speed = (emitter.speed ?? 0) + (emitter.speed_variation ?? 0) * (rand() - 0.5) * 2;
  const life = Math.max(
    0.05,
    (emitter.lifespan ?? FALLBACK_LIFESPAN) + emitter.lifespan_variation * (rand() - 0.5) * 2,
  );

  // The emission shape. A plane throws from a rectangle roughly upward, spread by the
  // two range fields; a sphere throws outward from a point in every direction. Anything
  // else the reader saw is treated as a plane, which is what most spell emitters are.
  const areaX = (emitter.area_length ?? 0) * (rand() - 0.5);
  const areaY = (emitter.area_width ?? 0) * (rand() - 0.5);

  // The two ranges are a cone in three dimensions, not one flat spread: vertical_range
  // opens the cone away from straight up, horizontal_range turns it around that axis.
  // Adding them together — which is the obvious mistake — gives a wedge that belongs to
  // neither. They are used as the angles they are and the result is projected, so an
  // emitter with a full 2π turn and no vertical opening reads as a ring seen edge-on,
  // which is what it is.
  const polar = emitter.kind === "sphere"
    ? Math.acos(1 - 2 * rand())            // even over a sphere, not bunched at the poles
    : (emitter.vertical_range ?? 0) * rand();
  const azimuth = emitter.kind === "sphere"
    ? rand() * Math.PI * 2
    : (emitter.horizontal_range ?? 0) * rand();

  p.x = emitter.position[0] + areaX;
  p.y = -emitter.position[2] + areaY; // model Z is up; canvas Y grows downward
  p.vx = Math.sin(polar) * Math.cos(azimuth) * speed;
  p.vy = -Math.cos(polar) * speed;
  p.age = 0;
  p.life = life;
  p.tile = Math.floor(rand() * Math.max(1, emitter.tiles));
}

/** Advance a pool by `dt` seconds, respawning whatever died. */
export function step(
  pool: Particle[], emitter: ParticleEmitter, dt: number, rand: () => number,
): void {
  const gravity = emitter.gravity ?? 0;
  for (const p of pool) {
    p.age += dt;
    if (p.age >= p.life) {
      spawn(p, emitter, rand);
      continue;
    }
    // Model gravity pulls along -Z, which is down the canvas.
    p.vy += gravity * dt;
    p.x += p.vx * dt;
    p.y += p.vy * dt;
  }
}

/** Fill a pool with particles already spread across their lives, so nothing pops in. */
export function seed(emitter: ParticleEmitter, rand: () => number): Particle[] {
  const pool: Particle[] = [];
  for (let i = 0; i < population(emitter); i++) {
    const p: Particle = { x: 0, y: 0, vx: 0, vy: 0, age: 0, life: 1, tile: 0 };
    spawn(p, emitter, rand);
    // Start each one part-way through its life, or the first frame is an empty burst.
    p.age = rand() * p.life;
    p.x += p.vx * p.age;
    p.y += p.vy * p.age;
    pool.push(p);
  }
  return pool;
}

/** What one particle looks like right now: colour, opacity and size for its age. */
export function appearance(emitter: ParticleEmitter, p: Particle) {
  const t = Math.min(1, p.age / p.life);
  const [r, g, b] = sample<[number, number, number]>(
    emitter.colors as [number, [number, number, number]][], t, [CHANNEL, CHANNEL, CHANNEL],
  );
  const alpha = sample<number>(emitter.alphas as [number, number][], t, 1);
  const [w, h] = sample<[number, number]>(
    emitter.scales as [number, [number, number]][], t, [0.05, 0.05],
  );
  return {
    r: Math.min(CHANNEL, Math.max(0, r)) / CHANNEL,
    g: Math.min(CHANNEL, Math.max(0, g)) / CHANNEL,
    b: Math.min(CHANNEL, Math.max(0, b)) / CHANNEL,
    alpha: Math.min(1, Math.max(0, alpha)),
    w, h,
  };
}

/**
 * How this emitter composites.
 *
 * The sprites are premultiplied and authored to be added onto black, which is what
 * makes an effect glow. `lighter` is that same sum, so an additive emitter reads the
 * way the model asks for; anything else draws normally.
 */
export function compositeFor(blend: string): GlobalCompositeOperation {
  return blend.startsWith("additive") ? "lighter" : "source-over";
}

/** Colour steps the tint cache rounds to. Finer than the eye needs, coarse enough to cache. */
const TINT_STEPS = 12;

/**
 * The sprite multiplied by a colour.
 *
 * An effect's texture is a shape — a glow, a spark, a shockwave — and its colour comes
 * from the emitter's own curve, so the two have to be combined. Canvas has no per-draw
 * tint and building one buffer per particle would mean a thousand canvases a frame, so
 * the colour is rounded to a step and the tinted sprite kept. A spell settles into a few
 * dozen distinct tints, which is a cache and not a leak.
 *
 * `multiply` keeps the sprite's own alpha, which is what carries the shape; a plain fill
 * would paint a coloured rectangle over it.
 */
export function tinted(
  image: HTMLImageElement,
  r: number, g: number, b: number,
  cache: Map<string, HTMLCanvasElement>,
): CanvasImageSource {
  const qr = Math.round(r * TINT_STEPS);
  const qg = Math.round(g * TINT_STEPS);
  const qb = Math.round(b * TINT_STEPS);
  // A sprite the curve leaves white needs no buffer at all.
  if (qr === TINT_STEPS && qg === TINT_STEPS && qb === TINT_STEPS) return image;

  const key = `${image.src}|${qr},${qg},${qb}`;
  const found = cache.get(key);
  if (found) return found;

  const buffer = document.createElement("canvas");
  buffer.width = image.width;
  buffer.height = image.height;
  const ctx = buffer.getContext("2d");
  if (!ctx) return image;

  ctx.drawImage(image, 0, 0);
  ctx.globalCompositeOperation = "multiply";
  ctx.fillStyle = `rgb(${Math.round((qr / TINT_STEPS) * 255)},`
    + `${Math.round((qg / TINT_STEPS) * 255)},`
    + `${Math.round((qb / TINT_STEPS) * 255)})`;
  ctx.fillRect(0, 0, buffer.width, buffer.height);
  // Multiply alone would also multiply the transparent margin into blackness, so the
  // sprite's own alpha is punched back over the result.
  ctx.globalCompositeOperation = "destination-in";
  ctx.drawImage(image, 0, 0);

  cache.set(key, buffer);
  return buffer;
}

/** A small deterministic generator, so a replay looks the same twice. */
export function seededRandom(seed: number): () => number {
  let state = seed || 1;
  return () => {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
}
