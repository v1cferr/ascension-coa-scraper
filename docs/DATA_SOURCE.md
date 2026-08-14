# Data source: discovery and validation

This documents where the scraper's data comes from, how that was determined, and how to
re-check it after Ascension redeploys the site.

## Summary

| | |
|---|---|
| Page | `https://ascension.gg/en/v2/coa-builder/<realm>` |
| Transport | A single HTTPS `GET`. No API key, no session, no browser. |
| Shape | Next.js App Router page; the whole talent dataset ships inside the server-rendered HTML as a React Server Components ("Flight") payload. |
| Size | ~12 MB of HTML, of which ~8.6 MB is the talent payload. |
| Icons | One CSS sprite sheet, `https://ascension.gg/icon/coa-builder-icon.webp`, addressed by `background-position` rules in a Next.js CSS chunk. |
| Class emblem + colour | A lookup table compiled into a JS chunk, mirrored in `classmeta.py`. |

## Why there is no browser automation

The original plan allowed for Playwright. It is not needed, and that is worth stating
explicitly so nobody re-adds it: the builder is server-rendered, so the payload is
already in the HTML response before any JavaScript runs. No XHR or `fetch` call to a
JSON API is required to obtain the talent data — the client components are hydrated from
the inline payload.

There *is* an internal `api/v3` service behind the site (the payload's own `meta` field
mentions an `"api/v3 builder CoA parser"` build step), but the builder page does not call
it at runtime for talent data, and it is not part of the documented surface. The
server-rendered payload is the stable, observable source, so that is what we read.

## How the payload was located

1. **Fetch the page and confirm it is Next.js SSR.**

   ```bash
   curl -s https://ascension.gg/en/v2/coa-builder/voljin -o page.html
   grep -c 'self.__next_f.push' page.html      # non-zero -> Flight payload present
   ```

2. **Reconstruct the Flight stream.** Next.js splits the payload across several
   `self.__next_f.push([1, "<fragment>"])` calls. Concatenating the fragments in document
   order rebuilds it. This is `flight.extract_payload`.

3. **Split the stream into rows.** Each row is `<hex-id>:<body>`. Most bodies run to the
   next newline; some are length-prefixed (`T<hex-bytes>,` for text, `o<hex-bytes>,` in
   segment-prefetch streams) and contain newlines of their own, so they must be consumed
   by byte count. Getting this wrong silently swallows the rows that follow. This is
   `flight.parse_rows`.

4. **Find the realm objects.** Rather than hard-coding a row id and prop path — both
   change on every rebuild — `discovery.find_realms` walks the decoded rows for objects
   carrying a `talents` mapping that contains `classes` and `entriesByTab`.

   At the time of writing, the page yields two realms: `voljin-alpha` (id 39) and
   `voljin` (id 40), each with 21 classes and 91 class/tab combinations.

## Upstream payload shape

```jsonc
{
  "id": 40,
  "slug": "voljin",
  "name": "Vol'Jin",
  "max_level": 60,
  "schema_version": { "talents": 2 },
  "talents": {
    "meta": { "runtimeBuildProcess": "...", "runtimeDescriptionPreference": "..." },
    "classes": [
      { "classId": 16, "className": "Stormbringer",
        "tabs": [ { "tabId": 42, "tabName": "Lightning", "sortOrder": 1 } ] }
    ],
    "entriesByTab": { "16:42": [ /* talent entries */ ] },
    "essenceByClass": { "16": { "maxTalentEssence": 25, "maxAbilityEssence": 26 } }
  }
}
```

A talent entry carries 26 fields, uniformly populated:

```jsonc
{
  "x": 1, "y": 6, "id": 6851, "name": "Lightning Rod",
  "flags": 0, "group": 0, "tabId": 42, "classId": 16,
  "aeCost": 0, "teCost": 1, "reqTabAE": 0, "reqTabTE": 8,
  "spellId": 300609, "spellIds": [300609],
  "iconPath": "Interface\\Icons\\inv_rod_enchantedcobalt",
  "nodeType": "SpendCircle", "entryType": "Talent",
  "isPassive": 0, "maxPoints": 1, "sortOrder": 0, "requiredLevel": 0,
  "isStartingNode": 0,
  "description": "<span ...>pre-rendered tooltip HTML</span>",
  "requiredIds": [0, 0, 0],
  "connectedNodeIds": [7769, 34674, 0, 0, /* ...padded to 15 */],
  "rankDescriptions": [ { "rank": 1, "spellId": 300609, "description": "..." } ]
}
```

Quirks that `normalize.py` absorbs:

- `requiredIds` and `connectedNodeIds` are fixed-width arrays zero-padded to 3 and 15.
- `group` uses `0` for "no choice group"; non-zero values pair two mutually exclusive nodes.
- `isStartingNode` is an integer that is not always 0 or 1 (`127` occurs).
- `entryType` is `Talent` or `Ability`; `nodeType` is `SpendCircle`, `SpendSquare`, or `SpendHex`.
- Descriptions are pre-rendered tooltip HTML, not plain text.

## How icons resolve

Entries reference icons by game path, never by URL. The frontend reduces the path to a
CSS class and renders `<span class="coa-builder-icon inv_rod_enchantedcobalt">`. The
stylesheet then places that class on one cell of a single sheet:

```css
.coa-builder-icon{background:url(/icon/coa-builder-icon.webp) 50% no-repeat}
.coa-builder-icon.inv_rod_enchantedcobalt{background-position:59.2593% 57.4074%;
                                          background-size:5500%,5500%}
```

`background-size: 5500%` means the sheet is 55 cells wide, and CSS percentage positioning
places cell `i` at `i / (N - 1) * 100%`. Inverting that gives integer cell coordinates,
which is what the dataset stores and what `--download-assets` uses to crop.

Observed at the time of writing: sheet is 3520x3520 (55x55 cells of 64x64), the CSS
defines 2964 cells, and the payload references 3002 distinct icon keys — so **about 79
icons have no cell**. Those render as broken on the site too; the dataset leaves their
`icon.sprite` null rather than inventing coordinates.

The path-to-class reduction is mirrored exactly in `icons.icon_key`, including the
leading-underscore rule for names starting with a digit (`5_archerskill01` ->
`_5_archerskill01`).

## Class emblems and colours

These are *not* in the page payload. They come from a table compiled into a JS chunk:

```js
let w={12:{classFile:"barbarian",color:"rgb(138, 51, 3)",rgb:"138, 51, 3"},...}
```

`classFile` is the emblem's sprite key and cannot be derived from the display name —
seven classes were renamed while keeping their original file:

| classId | Display name | classFile |
|---|---|---|
| 14 | Felsworn | `demonhunter` |
| 17 | Knight of Xoroth | `fleshwarden` |
| 19 | Templar | `monk` |
| 20 | Bloodmage | `sonofarugal` |
| 29 | Venomancer | `prophet` |
| 31 | Primalist | `wildwalker` |
| 32 | Runemaster | `spiritmage` |

Because it is bundled code rather than served data, it is mirrored in `classmeta.py`.
`scrape` warns when the payload contains a class id missing from that table.

To re-derive it, download the page's JS chunks and grep:

```bash
grep -oE '/_next/static/chunks/[a-zA-Z0-9_.-]+\.js' page.html | sort -u \
  | while read -r c; do curl -s "https://ascension.gg$c"; done \
  | grep -ohE '[0-9]+:\{classFile:"[a-z0-9_]+",color:"rgb\([^)]*\)"' | sort -u
```

## Validating after a site update

Run the scraper; it fails loudly and specifically when the source moves.

```bash
uv run ascension-coa list-classes                    # payload found and readable?
uv run ascension-coa scrape stormbringer --no-cache  # end-to-end
```

What the failure modes mean:

| Message | Meaning | Where to look |
|---|---|---|
| `no self.__next_f.push(...) fragments found` | Page is no longer server-rendered Next.js. | `flight.py`; re-run step 1 above. |
| `no realm payload found in the page` | The `talents`/`classes`/`entriesByTab` markers moved or were renamed. | `discovery.py`; dump row sizes and inspect the largest. |
| `class ... not found in realm ...` | Class renamed upstream; the error lists available slugs. | Nothing to fix — use the new name. |
| `no stylesheet ... defines .coa-builder-icon rules` | Sprite class or CSS chunk changed. Extraction continues without icon coordinates. | `icons.py`. |
| `no bundled metadata for class id N` | A class was added upstream. | Re-derive the table into `classmeta.py`. |

A **silent** change is the one to watch for: upstream adding fields. The normalized
models use `extra="forbid"`, so new fields surface when the raw payload is fed through
them in tests — but `normalize.py` reads the raw dict by key, so an added upstream field
is simply ignored until someone maps it. Compare a fresh payload's key set against the
26 fields listed above when investigating.

Two signals make drift easy to spot without reading diffs:

- `meta.content_hash` — SHA-256 over the normalized trees only. Stable across re-runs,
  changes exactly when talent data changes.
- `meta.upstream_schema_version` — the site's own `schema_version` field, currently
  `{"talents": 2}`. A bump here means the upstream shape changed on purpose.

## Etiquette

The scraper sends an identifying `User-Agent` pointing at this repository, makes one
request per resource, and caches responses in `.cache/` so repeated runs do not re-fetch
the 12 MB page or the 6 MB sprite sheet. Keep it that way.
