"use client";

import { cn } from "@/lib/utils";
import { iconUrl } from "@/lib/api";
import type { Icon as IconRef } from "@/lib/types";

/**
 * Two sources, because the data has two.
 *
 * A talent's icon is a cell of the builder's sprite sheet, addressed by integer
 * coordinates: CSS percentage positioning puts cell i at i/(N-1) across, which is the
 * inverse of how the site encodes it. Any other spell names a texture path instead,
 * which the server decodes for us — and that reaches every icon the client ships,
 * not the three thousand the sheet happens to hold.
 */

export function SpriteIcon(
  { icon, sheet, className }: { icon: IconRef | null; sheet: string | null; className?: string },
) {
  const s = icon?.sprite;
  const style = s && sheet
    ? {
        backgroundImage: `url("/data/${sheet}")`,
        backgroundSize: `${s.columns * 100}% ${s.rows * 100}%`,
        backgroundPosition:
          `${(s.column / (s.columns - 1)) * 100}% ${(s.row / (s.rows - 1)) * 100}%`,
      }
    : undefined;
  return (
    <span
      aria-hidden
      style={style}
      className={cn(
        "block bg-sunk bg-no-repeat border border-line2",
        !style && "opacity-40",
        className,
      )}
    />
  );
}

export function TextureIcon(
  { path, className }: { path: string | null; className?: string },
) {
  const url = iconUrl(path);
  return (
    <span
      aria-hidden
      style={url ? { backgroundImage: `url("${url}")` } : undefined}
      className={cn(
        "block bg-sunk border border-line2 bg-cover bg-center",
        !url && "opacity-40",
        className,
      )}
    />
  );
}
