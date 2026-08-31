# ascension-coa-scraper

Extract [Project Ascension](https://ascension.gg) into structured, reusable JSON —
talent trees from the website, and the spells, visual effects and sounds behind them
from the installed game client.

The two halves answer different questions and neither is sufficient alone. The builder
says a Stormbringer talent grants spell 500041; the client says that spell is *Body of
Lightning*, draws `shaman_lightningbolt_impact_v2.mdx` in both hands on cast, and plays
`lightningbolt_saurfang_01.ogg`.

**The Ascension realms close in September 2026.** The website half of this data
disappears with them; the client half survives only as long as an installed copy does,
and the launcher rewrites its archives on patch day.

| | Source | Documented in |
|---|---|---|
| Talent trees | `ascension.gg`, one HTTP GET, no browser | [`docs/DATA_SOURCE.md`](docs/DATA_SOURCE.md) |
| Spells, effects, sounds, icons | The installed client's MPQ archives | [`docs/CLIENT_DATA.md`](docs/CLIENT_DATA.md) |

There is also a viewer for reading all of it — see [Viewer](#viewer).

Tracked in [V1C-74](https://v1cferr.atlassian.net/browse/V1C-74).

## Install

```bash
uv sync                  # core
uv sync --extra assets   # adds Pillow, required for --download-assets
```

Reading the game client additionally needs StormLib, which is loaded at runtime and
never compiled here:

```bash
export ASCENSION_STORMLIB=$(nix build --no-link --print-out-paths nixpkgs#stormlib)/lib/libstorm.so
```

## Usage

### Talent trees, from the website

```bash
uv run ascension-coa list-classes
uv run ascension-coa scrape stormbringer --out data/voljin
uv run ascension-coa scrape stormbringer --realm-slug voljin-alpha --out data/voljin-alpha
```

`scrape` takes a class name, slug, or numeric id, and is not special-cased for any
class — `scrape necromancer` or `scrape 23` work the same way.

| Option              | Default           |                                                                            |
| ------------------- | ----------------- | -------------------------------------------------------------------------- |
| `--out`             | `data`            | Output directory                                                           |
| `--realm`           | `voljin`          | Realm slug in the builder URL                                              |
| `--realm-slug`      | same as `--realm` | Realm to read from the payload; a page lists several (e.g. `voljin-alpha`) |
| `--download-assets` | off               | Crop this class's icons out of the sprite sheet                            |
| `--cache-dir`       | `.cache`          | Cached HTTP responses                                                      |
| `--no-cache`        | off               | Always re-download                                                         |

### Spells, effects and sounds, from the client

```bash
uv run ascension-coa client inventory                 # what the archives hold
uv run ascension-coa client dump-dbc                  # decode tables to JSON
uv run ascension-coa client effects  --dataset data/voljin/stormbringer \
                                     --out data/client/effects/stormbringer.json
uv run ascension-coa client extract  --from-effects data/client/effects/stormbringer.json \
                                     --icons --out data/client/assets
```

`effects` takes its spell ids from a scraped dataset, which is what joins the two
halves: the builder says which spells a class has, the client says what they look and
sound like. `extract` then writes those files out — resolving each model's `.skin`
geometry and `.blp` textures, so what lands on disk actually opens in a viewer.

The client is autodetected under Wine/Bottles prefixes; override with `--client` or
`$ASCENSION_CLIENT`. The archive index is cached in `.cache/`, since building it opens
77 archives; pass `--reindex` after the launcher patches.

## Output

```bash
data/voljin/stormbringer/
├── stormbringer.json     index: metadata, class info, pointers to trees
├── class.json            shared baseline tab
├── lightning.json
├── wind.json
├── maelstrom.json
└── assets/icons/*.webp   only with --download-assets

data/client/
├── inventory.json                 archives, their contents, conflict count
├── effects/stormbringer.json      spell -> models, sounds, icon, per cast moment
└── assets/                        the model, texture and sound files themselves
                                   (not versioned; extracted from your own install)
```

Each tree file repeats `meta` and `class`, so it stands alone — a consumer that wants one
tree never has to read the index.

```jsonc
{
  "meta": {
    "source": "https://ascension.gg/en/v2/coa-builder/voljin",
    "builder": "coa",
    "realm": { "id": 40, "slug": "voljin", "name": "Vol'Jin" },
    "scraped_at": "2026-08-13T12:00:00+00:00",
    "schema_version": 1,              // this project's schema
    "scraper_version": "0.1.0",
    "upstream_schema_version": { "talents": 2 },
    "content_hash": "sha256:7927c93e…",
    "talent_count": 156,
    "tree_count": 4
  },
  "class": { "id": 16, "name": "Stormbringer", "slug": "stormbringer",
             "color": "rgb(0, 125, 237)", "max_talent_essence": 25, "…": "…" },
  "tree": {
    "id": 42, "name": "Lightning", "slug": "lightning", "is_shared": false,
    "talents": [
      {
        "id": 6851, "name": "Lightning Rod", "slug": "lightning-rod",
        "entry_type": "talent", "node_shape": "circle",
        "is_passive": false, "max_ranks": 1,
        "position": { "x": 1, "y": 6 },
        "costs": { "talent_essence": 1, "ability_essence": 0 },
        "requirements": { "tree_talent_essence": 8, "level": 0, "talent_ids": [] },
        "spell_id": 300609, "spell_ids": [300609],
        "description_html": "<span …>…</span>",
        "description": "Damage dealt by Forked Lightning …",
        "ranks": [ { "rank": 1, "spell_id": 300609, "description": "…" } ],
        "connections": [7769, 34674],
        "choice_group": null,
        "icon": {
          "source_path": "Interface\\Icons\\inv_rod_enchantedcobalt",
          "key": "inv_rod_enchantedcobalt",
          "sprite": { "sheet_url": "https://ascension.gg/icon/coa-builder-icon.webp",
                      "column": 32, "row": 31, "columns": 55, "rows": 55 },
          "file": null
        }
      }
    ]
  }
}
```

Notes on the schema:

- **`description_html` vs `description`** — upstream ships pre-rendered tooltip HTML;
  both the original and a plain-text rendering are kept.
- **`connections`** — the tree graph, with upstream's zero padding removed.
- **`choice_group`** — non-null on mutually exclusive node pairs.
- **`icon.sprite`** — the builder has no per-icon URLs, only cells of one sheet, so an
  icon is a sheet URL plus integer cell coordinates. `null` for the ~79 icons the sheet
  does not define (broken on the site too). `icon.file` is set only by `--download-assets`.
- **`meta.content_hash`** — SHA-256 over the normalized trees, computed before local
  asset paths are applied, so it is unaffected by `--download-assets` and changes exactly
  when upstream talent data changes. This is what makes patch diffing possible.

The dataset committed to this repo is generated without `--download-assets`, so its
`icon.file` values are `null` and it stays self-consistent — extracted icons are build
output and are not versioned.

### Effects output

```jsonc
{
  "source_archives": { "Spell": "patch-D.MPQ", "SpellVisual": "patch-S.MPQ", "…": "…" },
  "spell_count": 173,
  "missing_spell_ids": [],          // referenced by the builder, absent from Spell.dbc
  "spells": [
    {
      "spell_id": 500041, "name": "Body of Lightning",
      "talents": ["Body of Lightning"],
      "icon": "Interface\\Icons\\_D3stormarmor",
      "models": ["shaman_lightningbolt_impact_v2.mdx", "leishen_lightning_precast.m2"],
      "sounds": ["Sound\\Spells\\lightningbolt_saurfang_01.ogg"],
      "kits": [
        { "slot": "cast", "kit_id": 21038,
          "models": { "left_hand": "shaman_lightningbolt_impact_v2.mdx",
                      "right_hand": "shaman_lightningbolt_impact_v2.mdx" },
          "sound": { "id": 44032, "name": "…", "files": ["Sound\\…\\lightningbolt_saurfang_01.ogg"] } },
        { "slot": "state", "kit_id": 21040,
          "models": { "chest": "leishen_lightning_precast.m2" }, "sound": null }
      ],
      "missile_model": null, "missile_sound": null
    }
  ]
}
```

`slot` is the moment of the cast (`precast`, `cast`, `impact`, `channel`, `state`,
`persistent_area`, …) and the keys under `models` are attachment points. Kits that
resolve to neither a model nor a sound are dropped rather than padding every spell.

## Viewer

`web/` is a static page that reads the JSON above: talent trees drawn from their real
grid positions and connections, icons cut from the sprite sheet, and for any talent the
models and sounds the client plays for it. No build step and no dependencies — the fonts
are vendored, so it keeps working offline.

```bash
uv run ascension-coa build-index      # writes data/index.json and data/search.json
uv run ascension-coa serve            # then open http://localhost:8000/web/
```

Re-run `build-index` after scraping a new class or resolving new effects; it records
what is on disk and nothing else.

`serve` binds loopback. `--lan` binds every interface so another machine can reach it,
and prints the address to hand over:

```bash
uv run ascension-coa serve --lan
#   http://192.168.1.10:8000/web/
```

Two things that has to get past. The bind, which `--lan` handles, and the host firewall,
which it cannot. On NixOS, transiently:

```bash
sudo nixos-firewall-tool open tcp 8000   # lasts until reboot or the next rebuild
```

Serving to a network publishes the whole directory to anyone who can reach the host,
with no authentication. Dot-prefixed paths are refused, which keeps `.git` off the wire;
nothing else is filtered. Fine for a home network you trust, and worth stopping when you
are done rather than leaving up.

Worth knowing:

- **The cast score** is the point of the thing. Effect slots are moments in a cast, so
  they are laid out as time: columns are moments (`precast`, `cast`, `impact`, …), rows
  are attachment points (hands, chest, world, …), and each sound plays on the beat it
  fires — provided `client extract` has written it.
- **Deep links.** `#voljin/stormbringer/lightning/31163` addresses one talent, so a
  find can be sent to someone rather than described.
- **Search** covers every talent in both realms by name or spell id. Press `/` to focus it.
- **Icons** come from the builder's sprite sheet, which the dataset addresses by cell.
  The ~79 icons the sheet never defined render as empty nodes — they are broken on the
  site too.
- **Seeing an effect.** Clicking a model in the score opens it: how it is built
  (geometry or pure particles, how many emitters, whether it blends additively — which
  is what makes an effect glow) and every texture it composites, decoded from BLP and
  shown on black the way the game draws them. Nothing renders the model; for a particle
  effect its sprites are very nearly the whole of its look.
- **The player** takes a spell's sounds as a playlist in cast order — precast, cast,
  impact — so you can walk the whole cast rather than clicking each beat.
- **Downloads.** Every file in a talent's list is a link, and two buttons bundle them:
  one spell, or a whole class. A bundle is not just the files the dataset names — a
  model alone opens to nothing, so each one brings its `.skin` geometry and the `.blp`
  textures it names inside itself. Arm of Thorim lists 13 files and bundles 52.
  Anything the extracted tree does not hold is listed in a `MISSING.txt` inside the zip
  rather than quietly left out.

Bundles are built by `serve` on request:

| | |
|---|---|
| `/_bundle/<realm>/<class>.zip` | every asset the class references — tens of MB |
| `/_bundle/<realm>/<class>/<spell id>.zip` | one spell's |
| `/_texture/<asset path>.blp` | that texture, decoded to PNG |
| `/_model/<asset path>.m2` | what the model is made of, as JSON |

Those are the only dynamic routes; everything else is a file on disk. All of them read
`data/client/assets/`, so they need `client extract` to have run — but no game install
and no StormLib at serve time. Texture decoding additionally needs Pillow
(`uv sync --extra assets`); without it that one route reports what to install and the
rest keep working.

Deep links reach an effect, not just a talent:
`#voljin/stormbringer/lightning/31163/SPELLS%5Cleishen_lightning_column.m2`.

## Re-running

Extraction is fully unattended and deterministic: same upstream data in, identical JSON
out apart from `meta.scraped_at`, which is a fresh timestamp every run. So a re-run
always shows a diff — compare `meta.content_hash` instead to tell whether the talent
data actually changed.

## Development

```bash
uv run pytest
uv run ruff check src tests
```

## License

MIT
