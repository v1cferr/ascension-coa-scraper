# Layouts

There is no layout component tree. `web/src/app/layout.tsx` sets the fonts and the
dark class; `page.tsx` owns the whole frame inline.

## The frame today

```
┌──────────────────────────────────────────────────────────────────────────┐
│ masthead   identity · ⌘K search · realm select ·      captured/classes/  │  79px
│                                                        talents           │
├───────────┬──────────────────────────────────┬───────────────────────────┤
│ rail      │ stage                            │ readout                   │
│ 232px     │ 1fr                              │ 400px                     │
│           │                                  │                           │
│ 21 class  │ class name + stats + bundle      │ chosen talent or spell:   │
│ buttons,  │ tree tabs                        │ icon, name, granted by,   │
│ each a    │ ── the tree, absolutely          │ chips, description,       │
│ colour    │    positioned on a 78px grid ──  │ files with downloads      │
│ bar +     │ legend                           │                           │
│ name +    │ ── cast score band ──            │ (own scroll, sticky)      │
│ count     │    play the cast, the stage,     │                           │
│           │    the score grid, the inspector │                           │
├───────────┴──────────────────────────────────┴───────────────────────────┤
│ player   transport · title · seek · volume · queue of sounds by moment   │  sticky
└──────────────────────────────────────────────────────────────────────────┘
```

## What is wrong with it

- **Three fixed columns and a sticky player** leave the tree — the thing people came
  for — in a middle column narrower than the tree often is, so it scrolls horizontally
  behind a fade.
- **The cast score lives below the tree**, so choosing a talent puts the answer off
  screen; you scroll away from the tree to read it, then back.
- **The rail is 21 flat buttons.** No grouping, no search, no sense of which classes
  are similar. Two realms hide behind a `<select>` in the masthead.
- **A bare spell has no home.** It borrows the readout while the tree behind it still
  shows an unrelated class, which reads as a bug.
- **The player is always mounted** and takes vertical space even when nothing is
  playing.
- **Nothing surfaces the 3D** that `three-m2loader` is about to make possible for 58%
  of models, and there is no obvious place to put it.
