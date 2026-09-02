"use client";

import { forwardRef, useImperativeHandle, useEffect, useRef, useState } from "react";
import { Pause, Play, SkipBack, SkipForward, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import { assetUrl, fileName, label } from "@/lib/api";
import type { Effects } from "@/lib/types";

export type PlayerHandle = {
  playFile: (file: string) => Promise<number>;
  duration: () => number;
};

type Track = { url: string; slot: string; name: string; unplayable?: boolean };

const clock = (s: number) =>
  Number.isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "0:00";

/**
 * A spell's sounds are a short ordered list — the precast, the cast, the impact — so
 * they are treated as a playlist and can be walked in cast order rather than clicked
 * one at a time.
 */
export const SoundPlayer = forwardRef<PlayerHandle, {
  fx: Effects | null; title: string; assetRoot: string;
}>(function SoundPlayer({ fx, title, assetRoot }, ref) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [index, setIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [length, setLength] = useState(0);
  const [volume, setVolume] = useState(80);

  useEffect(() => {
    const next: Track[] = [];
    for (const kit of fx?.kits ?? []) {
      for (const file of kit.sound?.files ?? []) {
        next.push({ url: assetUrl(assetRoot, file), slot: kit.slot, name: fileName(file) });
      }
    }
    for (const file of fx?.missile_sound?.files ?? []) {
      next.push({ url: assetUrl(assetRoot, file), slot: "missile", name: fileName(file) });
    }
    setTracks(next);
    setIndex(-1);
    audio.current?.pause();
  }, [fx, assetRoot]);

  const start = (at: number) => {
    const track = tracks[at];
    if (!track || !audio.current) return;
    setIndex(at);
    audio.current.src = track.url;
    audio.current.play().catch(() => markUnplayable(at));
  };

  const markUnplayable = (at: number) =>
    setTracks((list) => list.map((t, i) => (i === at ? { ...t, unplayable: true } : t)));

  useImperativeHandle(ref, () => ({
    playFile: (file: string) => {
      const url = assetUrl(assetRoot, file);
      const at = tracks.findIndex((t) => t.url === url);
      if (at >= 0) start(at);
      // Give the element a moment to report a duration for the caller to time by.
      return new Promise<number>((done) => setTimeout(() => done(audio.current?.duration ?? 0), 350));
    },
    duration: () => audio.current?.duration ?? 0,
  }));

  if (!tracks.length) return null;
  const current = tracks[index];

  return (
    <div className="sticky bottom-0 z-30 border-t border-line2 bg-panel/90 px-6 py-3 backdrop-blur">
      <audio
        ref={audio}
        preload="none"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        onDurationChange={(e) => setLength(e.currentTarget.duration)}
        onEnded={() => index < tracks.length - 1 && start(index + 1)}
        onError={() => index >= 0 && markUnplayable(index)}
      />

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Button size="icon" variant="outline" aria-label="Previous sound"
                  disabled={index <= 0} onClick={() => start(index - 1)}
                  className="size-7 rounded-full border-line2 bg-sunk text-dim hover:border-class hover:text-class">
            <SkipBack className="size-3 fill-current" />
          </Button>
          <Button size="icon" variant="outline"
                  aria-label={playing ? "Pause" : "Play"}
                  onClick={() => {
                    if (index < 0) return start(0);
                    if (audio.current?.paused) audio.current.play().catch(() => {});
                    else audio.current?.pause();
                  }}
                  className="size-8 rounded-full border-[color-mix(in_srgb,var(--class)_40%,transparent)] bg-sunk text-class hover:border-class">
            {playing ? <Pause className="size-3 fill-current" /> : <Play className="size-3 fill-current" />}
          </Button>
          <Button size="icon" variant="outline" aria-label="Next sound"
                  disabled={index >= tracks.length - 1} onClick={() => start(index + 1)}
                  className="size-7 rounded-full border-line2 bg-sunk text-dim hover:border-class hover:text-class">
            <SkipForward className="size-3 fill-current" />
          </Button>
        </div>

        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex items-baseline gap-3">
            <span className="whitespace-nowrap text-[12.5px] font-semibold">{title}</span>
            <span className="truncate font-mono text-[11px] text-dim">
              {current
                ? current.unplayable
                  ? `${current.name} — this browser could not play it`
                  : `${label(current.slot)} · ${current.name}`
                : `${tracks.length} sound${tracks.length === 1 ? "" : "s"}`}
            </span>
            <span className="ml-auto whitespace-nowrap font-mono text-[11px] text-faint">
              {clock(time)} / {clock(length)}
            </span>
          </div>
          <Slider
            value={[length ? (time / length) * 1000 : 0]}
            max={1000} step={1} aria-label="Seek"
            onValueChange={([v]) => {
              if (audio.current && Number.isFinite(length)) audio.current.currentTime = (v / 1000) * length;
            }}
          />
        </div>

        <label className="hidden items-center gap-2 md:flex">
          <Volume2 className="size-3.5 text-faint" />
          <Slider
            value={[volume]} max={100} step={1} aria-label="Volume"
            className="w-[74px]"
            onValueChange={([v]) => {
              setVolume(v);
              if (audio.current) audio.current.volume = v / 100;
            }}
          />
        </label>
      </div>

      <ul className="mt-3 flex flex-wrap gap-1">
        {tracks.map((track, i) => (
          <li key={track.url + i}>
            <button
              type="button"
              onClick={() => start(i)}
              aria-current={i === index}
              className={cn(
                "inline-flex items-baseline gap-2 rounded-sm border px-2.5 py-[3px] font-mono text-[10.5px]",
                i === index
                  ? "border-class bg-[color-mix(in_srgb,var(--class)_12%,transparent)] text-foreground"
                  : "border-line text-dim hover:border-line2 hover:text-foreground",
              )}
            >
              <span className={cn("text-[9px] uppercase tracking-wider",
                                  i === index ? "text-class" : "text-faint")}>
                {label(track.slot)}
              </span>
              {track.name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
});
