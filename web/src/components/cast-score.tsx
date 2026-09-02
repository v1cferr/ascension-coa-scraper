"use client";

import { Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { fileName, label, orderedAttachments, orderedSlots } from "@/lib/api";
import type { Effects } from "@/lib/types";

/**
 * Effect slots are moments in a cast, so they are laid out as time: columns are
 * moments in order, rows are attachment points, and each sound sits on the beat it
 * fires. Read across a row and you have what happens to one hand from precast to
 * impact; read down a column and you have everything happening at once.
 */
export function CastScore({
  fx, beat, onInspect, onPlaySound,
}: {
  fx: Effects;
  beat: string | null;
  onInspect: (path: string) => void;
  onPlaySound: (file: string) => void;
}) {
  const slots = orderedSlots(fx);
  const rows = orderedAttachments(fx);
  const kitFor = (slot: string) => fx.kits.find((k) => k.slot === slot);

  const cell = "bg-panel px-2.5 py-[7px] min-w-[132px]";
  const head = "sticky left-0 z-20 w-[108px] min-w-[108px] bg-sunk";

  return (
    <div className="overflow-x-auto">
      <div
        className="grid min-w-max gap-px rounded-sm border border-line bg-line"
        style={{ gridTemplateColumns: `auto repeat(${slots.length}, minmax(132px, 1fr))` }}
      >
        <div className={cn(cell, head)} />
        {slots.map((slot) => (
          <div
            key={slot}
            className={cn(
              cell, "eyebrow bg-sunk !text-class transition-colors",
              beat === slot && "!bg-class !text-ink",
            )}
          >
            {label(slot)}
          </div>
        ))}

        {rows.map((attach) => (
          <div key={attach} className="contents">
            <div className={cn(cell, head, "truncate font-mono text-[11px] text-dim")}>
              {label(attach)}
            </div>
            {slots.map((slot) => {
              const model = kitFor(slot)?.models[attach];
              return (
                <div
                  key={slot}
                  className={cn(
                    cell,
                    model && "bg-[color-mix(in_srgb,var(--class)_7%,var(--panel))]",
                    beat === slot && "bg-[color-mix(in_srgb,var(--class)_22%,var(--panel))]",
                  )}
                >
                  {model && (
                    <button
                      type="button"
                      title={`${model}\nShow what this draws`}
                      onClick={() => onInspect(model)}
                      className="block w-full break-all text-left font-mono text-[11px] leading-snug hover:underline hover:decoration-class"
                    >
                      {fileName(model)}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ))}

        <div className={cn(cell, head, "font-mono text-[11px] text-dim")}>sound</div>
        {slots.map((slot) => {
          const sound = kitFor(slot)?.sound;
          const file = sound?.files[0];
          return (
            <div
              key={slot}
              className={cn(
                cell,
                sound && "bg-[color-mix(in_srgb,var(--class)_7%,var(--panel))]",
                beat === slot && "bg-[color-mix(in_srgb,var(--class)_22%,var(--panel))]",
              )}
            >
              {file && (
                <div className="flex items-center gap-2">
                  <Button
                    size="icon"
                    variant="outline"
                    aria-label={`Play ${fileName(file)}`}
                    onClick={() => onPlaySound(file)}
                    className="size-5 shrink-0 rounded-full border-line2 bg-sunk text-dim hover:border-class hover:text-class"
                  >
                    <Play className="size-2.5 fill-current" />
                  </Button>
                  <span className="break-all font-mono text-[10.5px] text-dim">
                    {fileName(file)}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
