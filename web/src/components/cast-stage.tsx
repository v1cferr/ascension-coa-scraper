"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { label, modelInfo, textureUrl } from "@/lib/api";
import type { Effects, Kit, ModelInfo, ParticleEmitter } from "@/lib/types";
import { ParticleStage } from "@/components/particle-stage";

export type Beat = { slot: string; sound: string | null };

/**
 * Playing the cast. Not a render — see EffectInspector for why. What plays is the cast
 * as the data describes it: the moments in order, each one's sprites shown and blended
 * the way its own emitters declare, the score column lit as it fires, and the sound on
 * its beat setting how long that beat lasts.
 */
export function CastStage({
  fx, onBeat, onSound, soundDuration,
}: {
  fx: Effects;
  onBeat: (slot: string | null) => void;
  onSound: (file: string) => Promise<number>;
  soundDuration: () => number;
}) {
  // One piece of state, carrying the spell it belongs to. A different spell makes it
  // stale, so "stopped and empty" is derived rather than set — which is what kept
  // tripping react-hooks/set-state-in-effect.
  const [stage, setStage] = useState<{
    spellId: number;
    playing: boolean;
    slot: string | null;
    frames: { path: string; additive: boolean }[];
    emitters: ParticleEmitter[];
  } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alive = useRef(true);

  useEffect(() => () => { alive.current = false; if (timer.current) clearTimeout(timer.current); }, []);

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setStage((s) => (s ? { ...s, playing: false } : s));
    onBeat(null);
  }, [onBeat]);

  const showBeat = useCallback(async (kit: Kit) => {
    onBeat(kit.slot);

    const paths = [...new Set(Object.values(kit.models))];
    const infos = await Promise.all(
      paths.map((p) => modelInfo(p).catch(() => null as ModelInfo | null)),
    );
    const seen = new Set<string>();
    const next: { path: string; additive: boolean }[] = [];
    const emitters: ParticleEmitter[] = [];
    for (const info of infos) {
      if (!info) continue;
      emitters.push(...(info.particles ?? []).filter((e) => e.texture));
      const blendFor = new Map(info.emitters.map((e) => [info.textures[e.texture]?.path, e.blend]));
      for (const texture of info.textures) {
        if (!texture.available || seen.has(texture.path)) continue;
        seen.add(texture.path);
        const blend = blendFor.get(texture.path) ?? info.blend_modes[0] ?? "";
        next.push({ path: texture.path, additive: blend.includes("additive") });
      }
    }
    setStage((s) => ({
      spellId: fx.spell_id, playing: s?.spellId === fx.spell_id ? s.playing : true,
      slot: kit.slot, frames: next, emitters,
    }));
  }, [onBeat, fx.spell_id]);

  const play = useCallback(async () => {
    const beats = fx.kits.filter((k) => Object.keys(k.models).length || k.sound);
    if (!beats.length) return;
    setStage({ spellId: fx.spell_id, playing: true, slot: null, frames: [], emitters: [] });

    let index = 0;
    const step = async () => {
      if (!alive.current || index >= beats.length) { stop(); return; }
      const kit = beats[index++];
      await showBeat(kit);
      if (!alive.current) return;

      let ms = 900;
      const file = kit.sound?.files[0];
      if (file) {
        await onSound(file);
        const seconds = soundDuration();
        if (Number.isFinite(seconds) && seconds > 0) {
          ms = Math.max(500, Math.min(seconds * 1000, 4000));
        }
      }
      timer.current = setTimeout(step, ms);
    };
    step();
  }, [fx, onSound, showBeat, soundDuration, stop]);

  // A new spell stops the clock. The stage itself needs no clearing: it carries the
  // spell it was built for, so it is already stale.
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    onBeat(null);
  }, [fx.spell_id, onBeat]);

  const playable = fx.kits.some((k) => Object.keys(k.models).length || k.sound);
  if (!playable) return null;

  const shown = stage?.spellId === fx.spell_id ? stage : null;
  const playing = !!shown?.playing;

  return (
    <div className="mb-4">
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <Button
          onClick={() => (playing ? stop() : void play())}
          className="gap-2 border border-[color-mix(in_srgb,var(--class)_40%,transparent)] bg-[color-mix(in_srgb,var(--class)_9%,var(--sunk))] text-foreground hover:bg-[color-mix(in_srgb,var(--class)_18%,var(--sunk))]"
        >
          {playing ? <Square className="size-3.5 fill-class text-class" />
                   : <Play className="size-3.5 fill-class text-class" />}
          {playing ? "Stop" : "Play the cast"}
        </Button>
        <p className="max-w-[52ch] text-[11.5px] text-dim">
          Each moment&apos;s emitters, run from their own speed, gravity, lifespan and
          colour, with the sound on its beat. The effect, not the caster: there is no
          character here, only what the spell draws.
        </p>
      </div>

      {shown?.slot && (
        <div className="rounded border border-line2 bg-black p-4">
          <div className="eyebrow mb-3 !text-class !tracking-[0.16em]">{label(shown.slot)}</div>
          {shown.emitters.length > 0 && (
            <ParticleStage emitters={shown.emitters} height={240} playing={playing} />
          )}
          <div className="mt-3 flex min-h-[132px] flex-wrap items-center gap-2.5">
            {shown.frames.length === 0 && (
              <p className="text-[12.5px] text-dim">This moment plays a sound and draws nothing.</p>
            )}
            {shown.frames.map((frame) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={frame.path}
                src={textureUrl(frame.path)}
                alt={frame.path}
                title={frame.path}
                className={cn(
                  "h-[124px] max-w-[240px] rounded-sm object-contain",
                  "animate-in fade-in zoom-in-95 duration-200",
                  frame.additive && "additive",
                )}
                onError={(e) => e.currentTarget.remove()}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
