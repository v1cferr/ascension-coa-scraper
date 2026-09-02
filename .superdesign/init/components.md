# Components

## shadcn primitives in use

`web/src/components/ui/` — badge, button, card, command, dialog, input, scroll-area,
separator, sheet, skeleton, slider, tabs, toggle, tooltip. Standard shadcn/new-york,
unmodified. `tooltip` is installed but not yet used anywhere.

## The project's own

| File | Does |
|---|---|
| `class-rail.tsx` | the 21-class list; a colour bar, a name, a talent count |
| `tree-canvas.tsx` | the tree: SVG connections behind absolutely-positioned icon buttons on a 78px grid; node shape carries meaning (circle = talent, square = ability, hex = capstone) and a dashed brace groups a choice pair |
| `cast-score.tsx` | the signature element: a grid whose columns are moments in a cast (precast → cast → impact → …) and whose rows are attachment points (hands, chest, world), with the sound on the beat it fires |
| `cast-stage.tsx` | plays that score: steps the moments, shows each one's sprites composited on black, sound sets the beat length |
| `effect-inspector.tsx` | what a model draws — its decoded textures and how it is built (particles vs geometry, emitter count, blending) |
| `sound-player.tsx` | the sticky player; a spell's sounds as a playlist in cast order |
| `spell-palette.tsx` | ⌘K; talents first, then any of 232,000 spells from the server |
| `granted-by.tsx` | which class grants a spell, and as what — Ability, Talent, TalentAbility, Trait |
| `icon.tsx` | `SpriteIcon` (a cell of the builder's sprite sheet, by integer coordinates) and `TextureIcon` (any icon, decoded from BLP by the server) |

## Data shapes

`web/src/lib/types.ts` is the contract with the Python service. The two that matter
for layout:

- **`Talent`** — grid `position`, `node_shape`, `entry_type`, `connections`,
  `choice_group`, `max_ranks`, `is_passive`, `costs`, `requirements`,
  `description_html`, `icon.sprite`.
- **`Effects`** — `kits[]`, each a moment: `slot`, `models` keyed by attachment point,
  `sound`. Plus `models[]`, `sounds[]`, `missile_model`.
