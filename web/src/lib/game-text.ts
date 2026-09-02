import type { ReactNode } from "react";
import { createElement, Fragment } from "react";

/**
 * Render the client's own tooltip markup.
 *
 * Spell.dbc stores colour as |cAARRGGBB … |r and breaks as |n, and refers to the
 * caster's stats with $-variables the server substitutes at cast time. The escapes
 * become real markup; the variables stay visible and marked, because inventing values
 * for them would be making the number up.
 */
export function gameText(raw: string): ReactNode {
  const out: ReactNode[] = [];
  let colour: string | null = null;
  let key = 0;

  for (const piece of raw.split(/(\|c[0-9a-fA-F]{8}|\|r|\|n)/g)) {
    if (!piece) continue;
    if (piece === "|n") { out.push(createElement("br", { key: key++ })); continue; }
    if (piece === "|r") { colour = null; continue; }
    const start = piece.match(/^\|c[0-9a-fA-F]{2}([0-9a-fA-F]{6})$/);
    if (start) { colour = `#${start[1]}`; continue; }

    const text = piece.replace(/\|[Hh][^|]*\|h/g, "").replace(/\|[Hh]/g, "");
    const parts = text.split(/(\$\{[^}]*\}|\$[a-zA-Z0-9]+)/g).filter(Boolean).map((bit) =>
      bit.startsWith("$")
        ? createElement("code", {
            key: key++,
            className:
              "rounded-sm border border-line bg-sunk px-1 font-mono text-[0.88em] text-dim",
            title: "Filled in by the server at cast time",
          }, bit)
        : bit,
    );
    out.push(
      colour
        ? createElement("span", { key: key++, style: { color: colour } }, ...parts)
        : createElement(Fragment, { key: key++ }, ...parts),
    );
  }
  return createElement(Fragment, null, ...out);
}
