"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { SpriteIcon } from "./icon";
import type { Talent } from "@/lib/types";

const CELL = 78;
const NODE = 54;

/**
 * The tree as the builder lays it out: integer grid positions, and connections drawn
 * between node centres. Shape carries meaning — the builder's own vocabulary, where a
 * circle is a talent, a square an ability and a hexagon a capstone — and a choice pair
 * is bracketed as the single decision it is.
 */
export function TreeCanvas({
  talents, sheet, selected, onSelect,
}: {
  talents: Talent[];
  sheet: string | null;
  selected: number | null;
  onSelect: (talent: Talent) => void;
}) {
  const { width, height, wires, braces } = useMemo(() => {
    const byId = new Map(talents.map((t) => [t.id, t]));
    const maxX = Math.max(0, ...talents.map((t) => t.position.x));
    const maxY = Math.max(0, ...talents.map((t) => t.position.y));
    const centre = (t: Talent) => ({
      x: t.position.x * CELL + CELL / 2,
      y: t.position.y * CELL + CELL / 2,
    });

    const wires: { a: number; b: number; x1: number; y1: number; x2: number; y2: number }[] = [];
    for (const t of talents) {
      for (const other of t.connections) {
        const target = byId.get(other);
        if (!target) continue;
        const p = centre(t);
        const q = centre(target);
        wires.push({ a: t.id, b: target.id, x1: p.x, y1: p.y, x2: q.x, y2: q.y });
      }
    }

    const groups = new Map<number, Talent[]>();
    for (const t of talents) {
      if (!t.choice_group) continue;
      groups.set(t.choice_group, [...(groups.get(t.choice_group) ?? []), t]);
    }
    const pad = 6;
    const braces = [...groups.values()].filter((g) => g.length > 1).map((g) => {
      const xs = g.map((t) => t.position.x * CELL + (CELL - NODE) / 2);
      const ys = g.map((t) => t.position.y * CELL + (CELL - NODE) / 2);
      return {
        key: g[0].id,
        left: Math.min(...xs) - pad,
        top: Math.min(...ys) - pad,
        width: Math.max(...xs) - Math.min(...xs) + NODE + pad * 2,
        height: Math.max(...ys) - Math.min(...ys) + NODE + pad * 2,
      };
    });

    return { width: (maxX + 1) * CELL, height: (maxY + 1) * CELL, wires, braces };
  }, [talents]);

  return (
    <div className="overflow-x-auto pb-2 [mask-image:linear-gradient(90deg,#000_0,#000_calc(100%-44px),transparent_100%)]">
      <div className="relative" style={{ width, height }}>
        <svg
          aria-hidden
          viewBox={`0 0 ${width} ${height}`}
          className="absolute inset-0 h-full w-full overflow-visible"
        >
          {wires.map((w, i) => (
            <line
              key={i}
              x1={w.x1} y1={w.y1} x2={w.x2} y2={w.y2}
              className={cn(
                "transition-colors",
                selected === w.a || selected === w.b
                  ? "stroke-class [stroke-width:2]"
                  : "stroke-line2 [stroke-width:1.5]",
              )}
            />
          ))}
        </svg>

        {braces.map((b) => (
          <div
            key={b.key}
            aria-hidden
            className="pointer-events-none absolute rounded-md border border-dashed border-line2"
            style={{ left: b.left, top: b.top, width: b.width, height: b.height }}
          />
        ))}

        {talents.map((t, i) => (
          <button
            key={t.id}
            type="button"
            title={t.name}
            aria-label={`${t.name}, ${t.entry_type}${t.is_passive ? ", passive" : ""}`}
            aria-pressed={selected === t.id}
            onClick={() => onSelect(t)}
            style={{
              left: t.position.x * CELL + (CELL - NODE) / 2,
              top: t.position.y * CELL + (CELL - NODE) / 2,
              width: NODE,
              height: NODE,
              animationDelay: `${Math.min(i * 8, 320)}ms`,
            }}
            className="group absolute animate-in fade-in zoom-in-95 duration-200 fill-mode-both"
          >
            <SpriteIcon
              icon={t.icon}
              sheet={sheet}
              className={cn(
                "h-full w-full transition-all",
                t.node_shape === "circle" && "rounded-full",
                t.node_shape === "square" && "rounded-[3px]",
                t.node_shape === "hex" &&
                  "rounded-[3px] [clip-path:polygon(50%_0,100%_25%,100%_75%,50%_100%,0_75%,0_25%)]",
                t.is_passive && "opacity-75",
                "group-hover:border-class group-hover:-translate-y-px",
                "group-hover:shadow-[0_0_0_1px_var(--class),0_0_18px_-4px_var(--class)]",
                selected === t.id &&
                  "border-class shadow-[0_0_0_1px_var(--class),0_0_18px_-4px_var(--class)]",
              )}
            />
            {t.max_ranks > 1 && (
              <span className="absolute -bottom-1.5 -right-1 rounded-sm border border-line2 bg-ink px-[3px] font-mono text-[10px] leading-none text-dim">
                ×{t.max_ranks}
              </span>
            )}
            {t.is_passive && (
              <span aria-hidden className="absolute bottom-[3px] right-[3px] h-[5px] w-[5px] rounded-full bg-dim" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
