"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { textureUrl } from "@/lib/api";
import type { ParticleEmitter } from "@/lib/types";
import {
  appearance, compositeFor, fitScale, seed, seededRandom, settle, step, tinted,
} from "@/lib/particles";

/**
 * The effect, running.
 *
 * Every number driving this comes out of the model: where particles are born, how fast
 * and which way they are thrown, how long they live, and what colour, opacity and size
 * they are at each point in that life. Nothing here is styled — the interface's own
 * accent deliberately stays out, because the whole purpose is to see the colour the
 * client ships rather than the colour this viewer prefers.
 *
 * Drawn on black with `lighter` where the emitter blends additively, which is the same
 * sum the game performs on these premultiplied sprites. Any other ground would lie
 * about what the effect looks like.
 */
export function ParticleStage({
  emitters, height = 320, playing = true,
}: {
  emitters: ParticleEmitter[];
  height?: number;
  playing?: boolean;
}) {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [loaded, setLoaded] = useState<Map<string, HTMLImageElement>>(new Map());

  // Only emitters that name a texture can be drawn at all. Memoised because both
  // effects below depend on it, and a fresh array each render would restart the
  // simulation on every unrelated repaint.
  const drawable = useMemo(() => emitters.filter((e) => e.texture), [emitters]);

  // Load each distinct sprite once. A texture that fails to decode simply drops its
  // emitter rather than taking the whole stage down with it.
  useEffect(() => {
    let alive = true;
    const paths = [...new Set(drawable.map((e) => e.texture as string))];
    if (!paths.length) return;

    Promise.all(paths.map((path) => new Promise<[string, HTMLImageElement] | null>((done) => {
      const image = new Image();
      image.crossOrigin = "anonymous";
      image.onload = () => done([path, image]);
      image.onerror = () => done(null);
      image.src = textureUrl(path);
    }))).then((pairs) => {
      if (!alive) return;
      setLoaded(new Map(pairs.filter(Boolean) as [string, HTMLImageElement][]));
    });

    return () => { alive = false; };
  }, [drawable]);

  useEffect(() => {
    const element = canvas.current;
    if (!element || !loaded.size) return;
    const ctx = element.getContext("2d");
    if (!ctx) return;

    const ratio = window.devicePixelRatio || 1;
    const width = element.clientWidth;
    element.width = width * ratio;
    element.height = height * ratio;
    ctx.scale(ratio, ratio);

    // A fixed seed per mount, so watching the same spell twice shows the same thing.
    const rand = seededRandom(drawable.length * 7919 + width);
    const pools = drawable.map((e) => seed(e, rand));
    // Let the effect run a moment before measuring it, or the scale is taken from a
    // burst that has not spread yet and every effect arrives too large.
    settle(drawable, pools, rand);
    const scale = fitScale(drawable, pools, Math.min(width, height));
    const originX = width / 2;
    const originY = height * 0.62; // the caster's feet sit below centre, as in game

    const tints = new Map<string, HTMLCanvasElement>();
    let frame = 0;
    let last = performance.now();

    const draw = (now: number) => {
      // Clamp the step: a backgrounded tab returns a delta of seconds and every
      // particle would jump its whole life in one frame.
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;

      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, width, height);

      drawable.forEach((emitter, i) => {
        const image = loaded.get(emitter.texture as string);
        if (!image) return;
        const pool = pools[i];
        if (playing) step(pool, emitter, dt, rand);

        ctx.globalCompositeOperation = compositeFor(emitter.blend);
        const cols = Math.max(1, emitter.cols);
        const rows = Math.max(1, emitter.rows);
        const tileW = image.width / cols;
        const tileH = image.height / rows;

        for (const p of pool) {
          const look = appearance(emitter, p);
          if (look.alpha <= 0.01) continue;

          const w = Math.max(1, look.w * scale);
          const h = Math.max(1, look.h * scale);
          const x = originX + p.x * scale;
          const y = originY + p.y * scale;

          // The sprite carries shape; the colour comes from the emitter's own curve, so
          // the two have to be multiplied. Canvas has no per-draw tint, and tinting per
          // particle would cost a buffer per particle, so the colour is quantised and
          // the tinted sprite cached — a few dozen buffers instead of a thousand.
          ctx.globalAlpha = look.alpha;
          const sprite = tinted(image, look.r, look.g, look.b, tints);

          const sx = (p.tile % cols) * tileW;
          const sy = Math.floor(p.tile / cols) % rows * tileH;
          ctx.drawImage(sprite, sx, sy, tileW, tileH, x - w / 2, y - h / 2, w, h);
        }
      });

      ctx.globalAlpha = 1;
      frame = requestAnimationFrame(draw);
    };

    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [loaded, height, playing, drawable]);

  if (!drawable.length) {
    return (
      <p className="border border-line bg-sunk px-3 py-6 text-center font-mono text-[11px] text-faint">
        This effect names no emitter texture, so there is nothing to run.
      </p>
    );
  }

  // Capped rather than full-bleed: effects are radial, and a very wide box frames a
  // burst as a speck in a letterbox. The scale is taken from the shorter side, so a
  // squarer stage is also a larger effect.
  return (
    <div className="flex justify-center border border-line bg-black">
      <canvas
        ref={canvas}
        style={{ height }}
        className="w-full max-w-[420px]"
        aria-label="The effect's particles, running from the model's own emitters"
      />
    </div>
  );
}
