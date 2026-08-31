"""Building the viewer manifest from what is on disk."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ascension_coa_scraper.index import IndexError_, build, build_search


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_class(root: Path, realm: str, slug: str, *, trees=("class", "fire"),
               realm_id: int = 40, scraped="2026-08-30T12:00:00+00:00"):
    directory = root / realm / slug
    tree_entries = [
        {"id": 10 + i, "name": name.title(), "slug": name, "sort_order": i,
         "is_shared": name == "class", "talent_count": 2, "file": f"{name}.json"}
        for i, name in enumerate(trees)
    ]
    write(directory / f"{slug}.json", {
        "meta": {"realm": {"id": realm_id, "slug": realm, "name": realm.title()},
                 "talent_count": 2 * len(trees), "tree_count": len(trees),
                 "scraped_at": scraped},
        "class": {"id": 16, "name": slug.title(), "slug": slug,
                  "color": "rgb(0, 125, 237)", "class_file": slug,
                  "max_talent_essence": 25, "max_ability_essence": 26, "icon": None},
        "trees": tree_entries,
    })
    for i, name in enumerate(trees):
        write(directory / f"{name}.json", {
            "meta": {"talent_count": 2},
            "tree": {"id": 10 + i, "name": name.title(), "slug": name, "talents": [
                {"id": 100 + i * 10 + n, "name": f"{name.title()} {n}", "spell_id": 900 + n}
                for n in range(2)
            ]},
        })
    return directory


def test_indexes_realms_and_classes(tmp_path):
    make_class(tmp_path, "voljin", "stormbringer")
    index = build(tmp_path)

    assert [r.slug for r in index.realms] == ["voljin"]
    realm = index.realms[0]
    assert realm.name == "Voljin" and realm.id == 40
    assert [c.slug for c in realm.classes] == ["stormbringer"]
    assert realm.classes[0].talent_count == 4
    assert realm.classes[0].dir == "voljin/stormbringer"


def test_trees_come_back_in_sort_order(tmp_path):
    make_class(tmp_path, "voljin", "s", trees=("class", "fire", "ice"))
    trees = build(tmp_path).realms[0].classes[0].trees
    assert [t.slug for t in trees] == ["class", "fire", "ice"]
    assert trees[0].is_shared and not trees[1].is_shared


def test_effects_are_matched_per_realm(tmp_path):
    # The realms reference different spells for the same class, so each gets its own
    # resolved effects and must not be handed the other's.
    make_class(tmp_path, "voljin", "s")
    make_class(tmp_path, "voljin-alpha", "s", realm_id=39)
    effects = tmp_path / "client" / "effects"
    write(effects / "voljin" / "s.json", {"spell_count": 7, "spells": []})
    write(effects / "voljin-alpha" / "s.json", {"spell_count": 9, "spells": []})

    index = build(tmp_path, effects_dir=effects)
    got = {r.slug: r.classes[0] for r in index.realms}
    assert got["voljin"].effects_spell_count == 7
    assert got["voljin"].effects_file == "client/effects/voljin/s.json"
    assert got["voljin-alpha"].effects_spell_count == 9


def test_a_flat_effects_file_still_indexes(tmp_path):
    make_class(tmp_path, "voljin", "s")
    effects = tmp_path / "client" / "effects"
    write(effects / "s.json", {"spell_count": 3, "spells": []})
    assert build(tmp_path, effects_dir=effects).realms[0].classes[0].effects_spell_count == 3


def test_a_class_without_effects_is_still_indexed(tmp_path):
    make_class(tmp_path, "voljin", "s")
    entry = build(tmp_path, effects_dir=tmp_path / "nowhere").realms[0].classes[0]
    assert entry.effects_file is None and entry.effects_spell_count == 0


def test_client_and_underscore_directories_are_not_realms(tmp_path):
    make_class(tmp_path, "voljin", "s")
    (tmp_path / "client").mkdir(exist_ok=True)
    (tmp_path / "_assets").mkdir()
    assert [r.slug for r in build(tmp_path).realms] == ["voljin"]


def test_the_newest_scrape_timestamp_is_recorded(tmp_path):
    make_class(tmp_path, "voljin", "a", scraped="2026-08-01T00:00:00+00:00")
    make_class(tmp_path, "voljin", "b", scraped="2026-08-30T00:00:00+00:00")
    assert build(tmp_path).captured == "2026-08-30T00:00:00+00:00"


def test_a_missing_sprite_sheet_is_reported_as_absent(tmp_path):
    make_class(tmp_path, "voljin", "s")
    assert build(tmp_path, sprite_sheet=tmp_path / "gone.webp").sprite_sheet is None


def test_a_present_sprite_sheet_is_recorded_relative_to_the_data_root(tmp_path):
    make_class(tmp_path, "voljin", "s")
    sheet = tmp_path / "_assets" / "sheet.webp"
    sheet.parent.mkdir()
    sheet.write_bytes(b"RIFF")
    assert build(tmp_path, sprite_sheet=sheet).sprite_sheet == "_assets/sheet.webp"


def test_an_empty_data_directory_is_an_error(tmp_path):
    with pytest.raises(IndexError_, match="no scraped datasets"):
        build(tmp_path)


def test_search_rows_carry_every_talent_once(tmp_path):
    make_class(tmp_path, "voljin", "s", trees=("class", "fire"))
    index = build(tmp_path)
    search = build_search(index, tmp_path)

    assert len(search["rows"]) == 4
    assert search["fields"] == ["name", "talent_id", "spell_id", "realm", "class", "tree"]
    names = {row[0] for row in search["rows"]}
    assert names == {"Class 0", "Class 1", "Fire 0", "Fire 1"}
    assert all(row[3] == "voljin" and row[4] == "s" for row in search["rows"])
