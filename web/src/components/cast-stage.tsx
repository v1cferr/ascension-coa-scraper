"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { label, modelInfo, textureUrl } from "@/lib/api";
import type { Effects, Kit, ModelInfo } from "@/lib/types";

export type Beat = { slot: string; sound: string | null };

/**
 * Playing the cast. Not a render — see EffectInspector for why. What plays is the cast
 * as the data describes it: the moments in order, each one's sprites shown and blended
 * the way its own emitters declare, the score column lit as it fires, and the sound on
 * its beat setting how long that beat lasts.
 */
export function CastStage({
  fx, onBeat, onSound, soundDuration, autoPlay,
}: {
  fx: Effects;
  onBeat: (slot: string | null) => void;
  onSound: (file: string) => Promise<number>;
  soundDuration: () => number;
  autoPlay?: boolean;
}) {
  const [playing, setPlaying] = useState(false);
  const [slot, setSlot] = useState<string | null>(null);
  const [frames, setFrames] = useState<{ path: string; additive: boolean }[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alive = useRef(true);

  useEffect(() => () => { alive.current = false; if (timer.current) clearTimeout(timer.current); }, []);

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setPlaying(false);
    onBeat(null);
  }, [onBeat]);

  const showBeat = useCallback(async (kit: Kit) => {
    setSlot(kit.slot);
    onBeat(kit.slot);

    const paths = [...new Set(Object.values(kit.models))];
    const infos = await Promise.all(
      paths.map((p) => modelInfo(p).catch(() => null as ModelInfo | null)),
    );
    const seen = new Set<string>();
    const next: { path: string; additive: boolean }[] = [];
    for (const info of infos) {
      if (!info) continue;
      const blendFor = new Map(info.emitters.map((e) => [info.textures[e.texture]?.path, e.blend]));
      for (const texture of info.textures) {
        if (!texture.available || seen.has(texture.path)) continue;
        seen.add(texture.path);
        const blend = blendFor.get(texture.path) ?? info.blend_modes[0] ?? "";
        next.push({ path: texture.path, additive: blend.includes("additive") });
      }
    }
    setFrames(next);
  }, [onBeat]);

  const play = useCallback(async () => {
    const beats = fx.kits.filter((k) => Object.keys(k.models).length || k.sound);
    if (!beats.length) return;
    setPlaying(true);

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

  useEffect(() => {
    stop();
    setSlot(null);
    setFrames([]);
    if (autoPlay) void play();
    // Re-arming on every spell would restart the cast mid-watch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fx.spell_id]);

  const playable = fx.kits.some((k) => Object.keys(k.models).length || k.sound);
  if (!playable) return null;

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
          Not a render — the client&apos;s own sprites, shown at the moment each one is
          drawn and blended the way the model declares, with the sound on its beat.
        </p>
      </div>

      {slot && (
        <div className="rounded border border-line2 bg-black p-4">
          <div className="eyebrow mb-3 !text-class !tracking-[0.16em]">{label(slot)}</div>
          <div className="flex min-h-[132px] flex-wrap items-center gap-2.5">
            {frames.length === 0 && (
              <p className="text-[12.5px] text-dim">This moment plays a sound and draws nothing.</p>
            )}
            {frames.map((frame) => (
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
