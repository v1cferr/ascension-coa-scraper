# Extractable components

Reusable beyond this page, in rough order of how well they would travel.

| Component | Why it travels | Props it would need |
|---|---|---|
| **CastScore** | a timeline grid whose columns are moments and rows are channels; nothing about it is WoW-specific | `columns`, `rows`, `cell(row, column)`, `footer(column)`, `active` |
| **SpriteGallery** | images composited on black with per-item blend mode and a labelled placeholder when one cannot decode | `items[{ src, caption, blend }]` |
| **CommandPalette** | two-source search — one local list, one server query — with grouped results | `groups[{ heading, items, onSelect }]`, `onQuery` |
| **MediaPlaylist** | one audio element, a queue with per-track labels, transport, seek, volume | `tracks[{ url, label, group }]` |
| **GraphCanvas** | nodes at integer grid positions with SVG connections, shape-coded, with grouping brackets | `nodes`, `edges`, `groups`, `cell`, `render(node)` |
| **AttributionList** | badge + name + qualifier + right-aligned meta | `items[{ kind, name, qualifier, meta }]` |

`TreeCanvas` as written is close to generic already; only the shape vocabulary and the
sprite-sheet icon are specific.
