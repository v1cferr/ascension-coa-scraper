# Pages

## `/` — `web/src/app/page.tsx`

The only page. A client component holding all state.

### Dependency tree

```
src/app/page.tsx
├── components/class-rail.tsx      → ui/scroll-area
├── components/tree-canvas.tsx     → components/icon.tsx
├── components/cast-score.tsx      → ui/button, lucide (Play)
├── components/cast-stage.tsx      → ui/button, lucide (Play, Square)
├── components/effect-inspector.tsx→ ui/badge, ui/button, ui/skeleton, lucide (X)
├── components/sound-player.tsx    → ui/button, ui/slider, lucide (transport icons)
├── components/spell-palette.tsx   → ui/command, ui/dialog, ui/badge, lucide
├── components/granted-by.tsx
├── components/icon.tsx
├── lib/api.ts        fetchers, caching, asset URL building, slot/attachment order
├── lib/types.ts      the service's shapes
├── lib/game-text.ts  renders the client's own |cAARRGGBB tooltip markup
└── lib/utils.ts      cn()
```

### State it holds

`index`, `realm`, `cls`, `treeRef`, `payload` (the loaded tree), `effects` (a Map from
spell id), `subject` (a talent in a tree, or a bare spell), `inspecting` (a model
path), `beat` (the moment currently playing), `paletteOpen`.

### The jobs a reader actually has

1. **Browse a class** — see its shape, its trees, how the talents connect.
2. **Read one talent** — what it does, costs, prerequisites.
3. **See and hear its effect** — which sprites, blended how, in what order, with what
   sound.
4. **Find a specific spell** among 232,000, including ones no tree names.
5. **Compare** — this class against that one, this effect against that one. *The
   interface currently supports this worst.*
6. **Take assets away** — one spell's, or a whole class's.
