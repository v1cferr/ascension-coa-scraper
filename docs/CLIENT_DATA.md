# Data source: the installed game client

[`DATA_SOURCE.md`](DATA_SOURCE.md) covers the website. This covers the other half: the
Ascension client on disk, which holds the spells, visual effects, sounds and icons that
the builder page only references by id.

The two are complementary and neither is sufficient. The builder says a Stormbringer
talent grants spell 500041; only the client says that spell 500041 is *Body of Lightning*,
draws `shaman_lightningbolt_impact_v2.mdx` in both hands on cast, holds
`leishen_lightning_precast.m2` on the chest while active, and plays
`lightningbolt_saurfang_01.ogg`.

## Summary

| | |
|---|---|
| Location | A WotLK 3.3.5a client, typically under a Wine/Bottles prefix. Autodetected; override with `$ASCENSION_CLIENT` or `--client`. |
| Archives | 77 MPQ v2 archives, ~43 GB, of which ~26 GB is Ascension's own content in 60 `patch-*` overlays. |
| Reader | StormLib via `ctypes`. Nothing is compiled at install time. |
| Plain files | `Data/Content/*.json` — ~90 MB of Ascension data outside any archive, no tooling needed. |
| Server-sent | `Cache/WDB/**/*.wdb` — populated only by playing, and not reproducible once the realm is gone. |

## What is irreplaceable

Worth stating plainly, because it decides what to back up first:

| | Size | Reproducible? |
|---|---|---|
| `common*.MPQ`, `expansion`, `lichking`, `patch`, `patch-2`, `patch-3` | 14.1 GB | Yes — any 3.3.5a client |
| `Data/enUS/*.MPQ` | 2.7 GB | Yes — stock Blizzard locale data |
| `Data/patch-*.MPQ` (60 archives) | 26.1 GB | **No** — Ascension custom content |
| `Data/Content/*.json` | 90 MB | **No** |
| `Cache/WDB/**` | ~10 MB | **No**, and it only grows while a realm is up |

The launcher rewrites the custom archives on patch day — several were replaced on
2026-08-28 — so "it is on disk" is not the same as "it is safe".

## Reading the archives

StormLib rather than a reimplementation, because WoW still uses PKWARE implode for some
blocks and a partial reader that mangles those silently is worse than no reader:

```bash
nix build --no-link --print-out-paths nixpkgs#stormlib
export ASCENSION_STORMLIB=<that path>/lib/libstorm.so
```

Any build works; the module also checks `ctypes.util.find_library("storm")`.

Archives are opened with `STREAM_FLAG_READ_ONLY`. That is not an optimisation — StormLib
will rewrite an archive opened for writing, and these archives are the only copy.

## Load order

Ascension ships content as overlay patches, so a path can exist in several archives and
the last one loaded wins. Vanilla 3.3.5a only defines the order for single-character
suffixes (`patch-4` … `patch-9`, then `patch-A` … `patch-Z`); Ascension adds `patch-CA`,
`patch-CHA`, `patch-WB1`, which vanilla would never load at all.

The rule used here, `install.PATCH_ORDER_RULE`:

> base archives in Blizzard's fixed order, then locale archives, then custom
> `patch-<suffix>` archives sorted by (length of suffix, suffix), so `patch-A` loads
> before `patch-CA`, which loads before `patch-CHA`. Later wins.
> Realm archives, declared in `Data/<realm>/listarchive`, load last.

**This is an assumption, not something read from the client.** It matters: 112,769 of
639,136 paths are provided by more than one archive. `ascension-coa client inventory`
prints the rule and the conflict count, and `Chain.conflicts` lists every contested
path, so a wrong guess is visible rather than silent.

## Where the tables actually are

Not where you would guess, and not all in one place:

| Table | Winning archive | Records | Blizzard's count |
|---|---|---|---|
| `Spell` | `area-52/patch-D.MPQ` | 239,062 | 46,583 |
| `SpellVisual` | `patch-S.MPQ` | 23,148 | 8,570 |
| `SpellVisualKit` | `patch-S.MPQ` | 29,584 | 7,000-odd |
| `SpellVisualEffectName` | `patch-S.MPQ` | 18,742 | 3,372 |
| `SpellIcon` | `patch-S.MPQ` | 16,396 | 3,105 |
| `SoundEntries` | `patch-M.MPQ` | 45,870 | 11,000-odd |

`patch-M.MPQ` (62 MB) carries 337 DBCs — the bulk of the custom table set — while the
spell family is overridden in `patch-S.MPQ` and `Spell.dbc` itself comes from the realm
overlay.

### The layout trap

DBC records are fixed-width four-byte fields with no type information, so column
meanings are external knowledge. A wrong schema does not fail; it decodes to plausible
nonsense.

This install carries **three generations of `Spell.dbc` at once**:

| Archive | Fields | Records |
|---|---|---|
| `enUS/locale-enUS.MPQ` | 222 | 38,003 |
| `enUS/patch-enUS.MPQ` | 239 | 46,583 |
| `patch-T.MPQ` | 234 | 209,509 |
| `area-52/patch-D.MPQ` | 234 | 239,062 |

A schema declaring the leading 204 columns "fits" all four by width and is correct for
only two. Schemas therefore pin the field counts they describe (`Table.known_widths`)
and the reader refuses any other. String offsets are range-checked against the string
block for the same reason.

Verified by decoding known spells from the 234-field table: Fireball (133), Power Word:
Shield (17), Frost Armor (168), Charge (100), Arcane Intellect (1459), Greater Heal
(2060) and Shadow Bolt (686) all come back with their expected names. Note that some
vanilla ids have been *repurposed* — 2050 is Lesser Heal upstream and Greater Heal here —
so a single mismatch is a content change, not a schema error, and the way to tell them
apart is to check several ids at once.

## The visual and sound chain

No table names a spell's effects directly. Four hops:

```
Spell.spellVisual[0]
  -> SpellVisual              a kit id per moment:
                              precast, cast, impact, channel, state, state_done,
                              caster_impact, target_impact, missile_targeting,
                              instant_area, impact_area, persistent_area
  -> SpellVisualKit           an effect id per attachment point:
                              head, chest, base, left/right hand, breath,
                              left/right weapon, world, special[3]
                              plus one sound id
  -> SpellVisualEffectName    .fileName  -> the .m2 / .mdx model path
  -> SoundEntries             .directoryBase + .file[10] -> the sound paths

Spell.spellIconID -> SpellIcon.textureFilename
SpellVisual.missileModel / .missileSound  (only when hasMissile is set)
```

`effects.EffectResolver` walks this and flattens it per spell. Kits resolving to neither
a model nor a sound are dropped rather than padding every spell with empty rows.

One incidental finding: Ascension's effects are largely imported from later retail
expansions — model names prefixed `7fx_`, `8fx_`, `9fx_` (Legion, Battle for Azeroth,
Shadowlands) sit alongside the WotLK-era `cfx_` and `.mdx` files.

## Plain-JSON data outside the archives

`Data/Content/` needs no MPQ tooling at all:

| File | Size | Holds |
|---|---|---|
| `CharacterAdvancementData.json` | 7.8 MB | The Wildcard/classless ability and talent catalogue: name, icon, class, tab, essence cost, quality, required level, spell ids |
| `SpellToSpellSuggestionData.json` | 12 MB | `{AlsoPick, PeopleWhoPick, RelevancyScore}` — which spells the playerbase actually combined, and how strongly. Aggregate build telemetry, and the one file here with no equivalent anywhere else |
| `SpellToEnchantmentSuggestionData.json` | 12 MB | The same shape, for enchantments per spell |
| `SpellRankData.json` | 807 KB | Rank chains: first spell id, rank, level, spell id |
| `SkillCardData.json` | 2.5 MB | Skill card entries, golden/lucky variants |
| `TradeSkillRecipeData.json` | 2.2 MB | Recipes |
| `HandOfFateQuestData.json` | 1.5 MB | Hand of Fate quests: level gates, required items, reward tables |
| `LFGData.json` | 85 KB | Dungeon finder tuning per dungeon, including tank/healer incentive amounts |
| `WorldMapAreaData.json` | 23 KB | Map areas with world-coordinate bounds |
| `ItemVariationData.json` | 3.8 MB | Item quality ladders (Heroic, Mythic, Bloodforged) |
| `Localization/{Spell,Item,Unit}/**.loc` | 43 MB | Name, Rank, Description and Tooltip in 8 locales |

Note the localisation files cover eight non-English locales; enUS strings live in the
DBCs.

## Usage

```bash
export ASCENSION_STORMLIB=<prefix>/lib/libstorm.so

ascension-coa client inventory --out data/client/inventory.json
ascension-coa client dump-dbc --out data/client/dbc
ascension-coa client effects --dataset data/voljin/stormbringer \
                             --out data/client/effects/stormbringer.json
ascension-coa client extract --from-effects data/client/effects/stormbringer.json \
                             --icons --out data/client/assets
```

The archive index is cached in `.cache/client-index.json`; building it opens all 77
archives and takes about a minute. Pass `--reindex` after the launcher patches.

## Validating after a client patch

| Symptom | Meaning |
|---|---|
| `could not load StormLib` | `$ASCENSION_STORMLIB` unset or stale after a `nix store gc`. |
| `no Ascension client found` | Prefix moved; set `$ASCENSION_CLIENT`. |
| `this schema describes the N-field layout` | The winning archive for that table changed generation. Check `client inventory` for a new archive, and re-derive the schema before widening `known_widths`. |
| `string offset ... outside the string block` | Almost always the same cause as above, caught one hop later. |
| A path is suddenly read from a different archive | The load-order assumption and a new archive name disagree; see `Chain.conflicts`. |
