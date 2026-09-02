"use client";

import { useEffect, useMemo, useState } from "react";
import { Play, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SpriteIcon, TextureIcon } from "@/components/icon";
import { cn } from "@/lib/utils";
import { ATTACHMENTS, MOMENTS, fileName, label, modelInfo, textureUrl } from "@/lib/api";
import type { Effects, ModelInfo } from "@/lib/types";
import type { Pin } from "@/lib/subject";

/**
 * The board exists because comparing is what two people designing a mod actually do,
 * and it was the one job the old layout supported worst — you had to hold one class's
 * effect in your head while navigating to another's.
 *
 * Cards are snapshots. Each keeps the accent it was pinned with, so a Stormbringer
 * talent beside a Pyromancer one reads blue against orange, and the cast scores line up
 * moment against moment.
 */
export function CompareBoard({
  pins, sheet, onRemove, onClear, onPlaySound,
}: {
  pins: Pin[];
  sheet: string | null;
  onRemove: (key: string) => void;
  onClear: () => void;
  onPlaySound: (file: string) => void;
}) {
  // Every card draws the same columns and the same rows — the union across the board,
  // in cast order — so a moment sits in the same place on every card and the rows
  // actually line up. Cards laid out on their own moments look aligned and are not:
  // one card's second column was precast where another's was impact.
  const shared = useMemo(() => {
    const slots = new Set<string>();
    const attachments = new Set<string>();
    for (const pin of pins) {
      for (const kit of pin.fx?.kits ?? []) {
        if (Object.keys(kit.models).length || kit.sound) slots.add(kit.slot);
        for (const attach of Object.keys(kit.models)) attachments.add(attach);
      }
    }
    return {
      slots: [
        ...MOMENTS.filter((m) => slots.has(m)),
        ...[...slots].filter((s) => !MOMENTS.includes(s as never)),
      ],
      attachments: [
        ...ATTACHMENTS.filter((a) => attachments.has(a)),
        ...[...attachments].filter((a) => !ATTACHMENTS.includes(a as never)),
      ],
    };
  }, [pins]);

  return (
    <>
      <div className="mb-4 flex items-center gap-3 border-b border-line pb-3">
        <h2 className="eyebrow">Compare</h2>
        <span className="font-mono text-[11px] text-dim">
          {pins.length} pinned
        </span>
        {pins.length > 0 && (
          <Button
            variant="ghost" size="sm" onClick={onClear}
            className="ml-auto h-6 px-2 text-[11px] text-dim hover:text-foreground"
          >
            Clear all
          </Button>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {pins.map((pin) => (
          <Card key={pin.key} pin={pin} sheet={sheet} shared={shared}
                onRemove={() => onRemove(pin.key)} onPlaySound={onPlaySound} />
        ))}
        <EmptyCard hasAny={pins.length > 0} />
      </div>
    </>
  );
}

function EmptyCard({ hasAny }: { hasAny: boolean }) {
  return (
    <div className="grid min-h-[220px] place-items-center rounded border border-dashed border-line2 p-6 text-center">
      <div>
        <Plus aria-hidden className="mx-auto mb-2 size-5 text-faint" />
        <p className="text-[12.5px] leading-snug text-dim">
          {hasAny ? "Pin another" : "Pin a talent or spell"} from the navigator to
          compare it here.
        </p>
      </div>
    </div>
  );
}

function Card({
  pin, sheet, shared, onRemove, onPlaySound,
}: {
  pin: Pin;
  sheet: string | null;
  shared: { slots: string[]; attachments: string[] };
  onRemove: () => void;
  onPlaySound: (file: string) => void;
}) {
  return (
    // The accent is set on the card, not inherited, which is what lets two cards from
    // different classes sit side by side without one repainting the other.
    <article
      style={{ ["--class" as string]: pin.accent }}
      className="rounded border border-line border-l-2 border-l-class bg-panel p-4"
    >
      <header className="mb-3 flex items-start gap-3">
        {pin.icon.kind === "sprite"
          ? <SpriteIcon icon={pin.icon.icon} sheet={sheet} className="size-10 shrink-0 rounded-sm" />
          : <TextureIcon path={pin.icon.path} className="size-10 shrink-0 rounded-sm" />}
        <div className="min-w-0 flex-1">
          <h3 className="display truncate text-[15px] font-semibold">{pin.name}</h3>
          <p className="font-mono text-[10.5px] text-dim">
            {pin.spellId ? `spell ${pin.spellId}` : "no spell"} · {pin.meta}
          </p>
        </div>
        <Button
          size="icon" variant="ghost" onClick={onRemove}
          aria-label={`Remove ${pin.name} from the board`}
          className="size-6 shrink-0 text-faint hover:text-foreground"
        >
          <X className="size-3.5" />
        </Button>
      </header>

      {pin.owners.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {pin.owners.map((owner, i) => (
            <span
              key={i}
              className={cn(
                "inline-flex items-baseline gap-1.5 rounded-sm px-1.5 py-px text-[9.5px] uppercase tracking-[0.08em]",
                owner.type === "Ability"
                  ? "bg-class font-semibold text-ink"
                  : "bg-line text-dim",
              )}
            >
              {owner.type}
              <span className="normal-case tracking-normal">{owner.class}</span>
              {owner.tab && <span className="font-mono normal-case tracking-normal opacity-70">{owner.tab}</span>}
            </span>
          ))}
        </div>
      )}

      {pin.fx ? (
        <>
          <MiniScore fx={pin.fx} shared={shared} />
          <Sprites fx={pin.fx} />
          <Sounds fx={pin.fx} onPlay={onPlaySound} />
        </>
      ) : (
        <p className="text-[12px] text-dim">
          The client plays no visual or sound for this one.
        </p>
      )}
    </article>
  );
}

/** The same column-is-a-moment, row-is-an-attachment grid, but on the board's shared
 *  axes rather than this spell's own, so two cards can be read against each other. */
function MiniScore({
  fx, shared,
}: { fx: Effects; shared: { slots: string[]; attachments: string[] } }) {
  const { slots, attachments: rows } = shared;
  const kitFor = (slot: string) => fx.kits.find((k) => k.slot === slot);

  return (
    <div className="mb-3 overflow-x-auto">
      <div
        className="grid min-w-max gap-px rounded-sm border border-line bg-line text-[10px]"
        style={{ gridTemplateColumns: `auto repeat(${slots.length}, minmax(84px, 1fr))` }}
      >
        <div className="bg-sunk px-2 py-1" />
        {slots.map((slot) => (
          <div key={slot} className="bg-sunk px-2 py-1 font-semibold uppercase tracking-[0.08em] text-class">
            {label(slot)}
          </div>
        ))}
        {rows.map((attach) => (
          <div key={attach} className="contents">
            <div className="sticky left-0 bg-sunk px-2 py-1 font-mono text-dim">{label(attach)}</div>
            {slots.map((slot) => {
              const model = kitFor(slot)?.models[attach];
              return (
                <div
                  key={slot}
                  title={model}
                  className={cn(
                    "truncate bg-panel px-2 py-1 font-mono",
                    model && "bg-[color-mix(in_srgb,var(--class)_8%,var(--panel))]",
                  )}
                >
                  {model ? fileName(model) : ""}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

/** The sprites the card's models composite, on black, which is how the game draws them. */
function Sprites({ fx }: { fx: Effects }) {
  const [paths, setPaths] = useState<string[]>([]);

  useEffect(() => {
    let live = true;
    const models = [...new Set(fx.models)];
    Promise.all(models.map((m) => modelInfo(m).catch(() => null as ModelInfo | null)))
      .then((infos) => {
        if (!live) return;
        const seen = new Set<string>();
        for (const info of infos) {
          for (const texture of info?.textures ?? []) {
            if (texture.available) seen.add(texture.path);
          }
        }
        setPaths([...seen].slice(0, 10));
      });
    return () => { live = false; };
  }, [fx]);

  if (!paths.length) return null;
  return (
    <div className="mb-3 flex gap-1.5 overflow-x-auto rounded-sm bg-black p-1.5">
      {paths.map((path) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={path} src={textureUrl(path)} alt={path} title={path} loading="lazy"
          className="size-11 shrink-0 rounded-sm object-contain"
          onError={(e) => e.currentTarget.remove()}
        />
      ))}
    </div>
  );
}

function Sounds({ fx, onPlay }: { fx: Effects; onPlay: (file: string) => void }) {
  const tracks = fx.kits.flatMap((kit) =>
    (kit.sound?.files ?? []).map((file) => ({ slot: kit.slot, file })));
  if (!tracks.length) return null;

  return (
    <ul className="flex flex-wrap gap-1">
      {tracks.map(({ slot, file }, i) => (
        <li key={`${file}-${i}`}>
          <button
            type="button" onClick={() => onPlay(file)}
            className="inline-flex items-center gap-1.5 rounded-sm border border-line px-1.5 py-0.5 font-mono text-[9.5px] text-dim hover:border-class hover:text-foreground"
          >
            <Play className="size-2 fill-current text-class" />
            <span className="uppercase tracking-wider text-faint">{label(slot)}</span>
            {fileName(file)}
          </button>
        </li>
      ))}
    </ul>
  );
}
