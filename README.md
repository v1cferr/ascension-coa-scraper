# ascension-coa-scraper

Extract and normalize [Project Ascension — Conquest of Azeroth](https://ascension.gg/en/v2/coa-builder/voljin)
talent trees into a structured, reusable JSON dataset.

The builder ships its entire talent dataset inside the server-rendered page, so this
scraper is plain HTTP — no browser automation required. See
[`docs/DATA_SOURCE.md`](docs/DATA_SOURCE.md) for how that was determined and how to
re-validate it after a site update.

## Status

Early development. Tracked in [V1C-74](https://v1cferr.atlassian.net/browse/V1C-74).

## Install

```bash
uv sync                      # core
uv sync --extra assets       # adds Pillow, needed for --download-assets
```

## Usage

```bash
uv run ascension-coa scrape stormbringer
uv run ascension-coa scrape stormbringer --download-assets
```

## License

MIT
