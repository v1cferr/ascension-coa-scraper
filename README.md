# ascension-coa-scraper

Extract and normalize [Project Ascension — Conquest of Azeroth](https://ascension.gg/en/v2/coa-builder/voljin)
talent trees into a structured, reusable JSON dataset.

The builder ships its entire talent dataset inside the server-rendered page, so this is
plain HTTP — **no browser automation**. How that was determined, and how to re-validate
it after a site update, is in [`docs/DATA_SOURCE.md`](docs/DATA_SOURCE.md).

Tracked in [V1C-74](https://v1cferr.atlassian.net/browse/V1C-74).

## Install

```bash
uv sync                  # core
uv sync --extra assets   # adds Pillow, required for --download-assets
```

## Usage

```bash
uv run ascension-coa scrape stormbringer
uv run ascension-coa scrape stormbringer --download-assets
uv run ascension-coa list-classes
```

`scrape` takes a class name, slug, or numeric id, and is not special-cased for any
class — `scrape necromancer` or `scrape 23` work the same way.

| Option | Default | |
|---|---|---|
| `--out` | `data` | Output directory |
| `--realm` | `voljin` | Realm slug in the builder URL |
| `--realm-slug` | same as `--realm` | Realm to read from the payload; a page lists several (e.g. `voljin-alpha`) |
| `--download-assets` | off | Crop this class's icons out of the sprite sheet |
| `--cache-dir` | `.cache` | Cached HTTP responses |
| `--no-cache` | off | Always re-download |

## Output

```
data/stormbringer/
├── stormbringer.json     index: metadata, class info, pointers to trees
├── class.json            shared baseline tab
├── lightning.json
├── wind.json
├── maelstrom.json
└── assets/icons/*.webp   only with --download-assets
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
- **`meta.content_hash`** — SHA-256 over the normalized trees only, so it is stable
  across re-runs and changes exactly when talent data changes. This is what makes patch
  diffing possible.

## Re-running

Extraction is fully unattended and deterministic: same upstream data in, byte-identical
JSON out. `content_hash` is the cheap way to tell whether a re-run actually changed
anything.

## Development

```bash
uv run pytest
uv run ruff check src tests
```

## License

MIT
