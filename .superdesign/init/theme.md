# Theme

Tailwind v4, tokens declared in `web/src/app/globals.css` under `:root` and mapped
into `@theme inline`. Dark only — the page sets `className="dark"` on `<html>`.

## The one rule the design is built on

The class colour ships in the dataset (`rgb(0, 125, 237)` for Stormbringer, a different
value for each of 21 classes) and is written to `--class` at runtime. It is the only
saturated colour on screen. Everything else is a near-black with a faint cold-green
cast — instrument housing, not the game's own gold-and-parchment.

## Tokens

| Token | Value | Role |
|---|---|---|
| `--ink` | `#0b0f0e` | page ground |
| `--panel` | `#101614` | raised surfaces, the readout, the player |
| `--raise` | `#151d1a` | secondary/muted surfaces |
| `--sunk` | `#080b0a` | inputs, wells, sticky row heads |
| `--line` | `#212c28` | hairlines |
| `--line-2` | `#2d3a35` | borders that need to read |
| `--text` | `#dce4df` | body |
| `--dim` | `#84948c` | captions, file paths |
| `--faint` | `#56645e` | eyebrows, disabled |
| `--class` | injected | the class colour; primary and ring both alias it |

shadcn's semantic tokens (`--background`, `--primary`, `--border`, …) are aliases onto
these, not the other way round.

## Type

| Role | Family | Notes |
|---|---|---|
| display / UI | Archivo (variable, `wdth` axis) | headings use `font-stretch: 118–124%` |
| data | IBM Plex Mono 400/500/600 | file paths, ids, blend modes, counts |

Loaded through `next/font/google` as `--font-archivo` / `--font-plex-mono`.

**Decided change:** Inter replaces Archivo for UI; a mono stays for technical data.

## Utility classes

- `.eyebrow` — 10px, 600, uppercase, `0.14em` tracking, `--faint`. Every column head
  and field label.
- `.display` — `-0.02em` tracking, stretched. Headings.
- `.additive` — `mix-blend-mode: screen`, for effect sprites, which are authored to be
  composited onto black.
