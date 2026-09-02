# Design system — Ascension archive viewer

## What this thing is

A reading tool for two people designing a World of Warcraft mod. It holds talent trees,
spells, visual effects and sounds extracted from a private server that shuts down in
September 2026. It is **the record of a game, not the game** — so no gold filigree, no
parchment, no fantasy ornament. The register is a records system: an instrument you
read data off.

Audience: two people, technical, using it daily for weeks. Density is a feature.
Discoverability matters less than being fast once you know it.

## Colour — non-negotiable

Ground is a near-black with a faint cold-green cast. Low saturation everywhere.

| Token | Hex | Role |
|---|---|---|
| `--ink` | `#0b0f0e` | page ground |
| `--panel` | `#101614` | raised surfaces, panels, the player |
| `--raise` | `#151d1a` | secondary/muted surfaces |
| `--sunk` | `#080b0a` | inputs, wells, sticky row heads |
| `--line` | `#212c28` | hairlines |
| `--line-2` | `#2d3a35` | borders that need to read |
| `--text` | `#dce4df` | body |
| `--dim` | `#84948c` | captions, file paths, secondary |
| `--faint` | `#56645e` | eyebrows, disabled |
| `--class` | **runtime** | the accent — see below |

**THE ONE RULE: `--class` is the only saturated colour on screen.** It ships in the
dataset — `rgb(0, 125, 237)` for Stormbringer, a different value for each of 21 classes
— and is written to a CSS custom property at runtime. Every accent, focus ring, active
state, chart mark and highlight derives from it. Changing class repaints the whole
interface from that one value.

**Therefore: never introduce a second accent colour.** No pink, no neon, no purple
gradient, no amber, no teal. No multi-colour palettes. If something needs to stand out,
it uses `--class` or it uses weight and space. Destructive is the single exception:
`#b4453a`.

Dark only. There is no light theme and none is wanted.

## Type — non-negotiable

| Role | Family | Notes |
|---|---|---|
| UI, headings, body | **Inter** | via `next/font/google`, `--font-inter` |
| All technical data | **JetBrains Mono** | 400/500/600, `--font-jetbrains` |

**No other typeface.** No serif, no display face, no decorative face, no Playfair, no
Georgia, no system-ui substitution.

The mono is structural, not stylistic. This interface is largely file paths
(`SPELLS\leishen_lightning_precast_nosparks.m2`), spell ids (`801847`), blend modes
(`additive`) and counts — a fixed advance keeps columns aligned and a slashed zero keeps
`0` from reading as `O`. **Anything that is data goes in mono. Anything that is prose or
a label goes in Inter.**

Inter has no width axis, so hierarchy comes from weight and tracking:

- `.eyebrow` — 10px, 600, uppercase, `0.13em` tracking, `--faint`. Every column head
  and field label.
- `.display` — headings; negative tracking (`-0.021em`), which is what Inter wants
  large.
- Body 13–14px. Data 10.5–12px mono.

## Shape and depth

- Radius: 4px (`--radius`). Small, not rounded-friendly. Circles only for icon buttons
  and talent nodes whose shape carries meaning.
- Borders over shadows. A hairline (`--line`) separates; `--line-2` when a border must
  read as an edge. Shadow is reserved for the one thing that glows: a selected talent
  node gets `0 0 0 1px var(--class), 0 0 18px -4px var(--class)`.
- No glassmorphism beyond the player's `backdrop-blur`, no neumorphism, no gradient
  fills except the masthead's `panel → ink`.

## Meaning carried by form

These are not decoration and must survive any redesign:

- **Talent node shape** — circle = talent, square = ability, hexagon = capstone. A
  dashed bracket groups a choice pair as the one decision it is.
- **Effect sprites on black** — they are premultiplied and authored to be composited
  onto black, with `mix-blend-mode: screen` where the model declares additive blending.
  Any other ground lies about what the effect looks like.
- **Ownership badges** — a filled `--class` badge for an ability the class simply has;
  a muted badge for a talent you spend a point on. That contrast is the point.

## Components

shadcn/ui, new-york style, with its semantic tokens aliased **onto** the tokens above —
never the other way round. Icons: lucide-react only.

Installed: badge, button, card, command, dialog, input, scroll-area, separator, sheet,
skeleton, slider, tabs, toggle, tooltip.

## Voice

Plain and specific. Say what a thing is, not how impressive it is. Where the data does
not support an answer, say so rather than guessing — the interface already does this in
places ("blending: set per emitter", "format not decodable", "this browser could not
play it") and that honesty is part of its character.

No marketing language. No "premium", "elegant", "powerful", "seamless". No hero
sections, no feature grids, no calls to action. Nobody is being sold anything.
