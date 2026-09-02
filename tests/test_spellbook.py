"""Resolving every spell in the client into a queryable book."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ascension_coa_scraper.client.spellbook import (
    SCHEMA_VERSION,
    build,
    connect,
    fetch,
    search,
)


class FakeInstall:
    """Only the part the builder reads: where the plain-JSON content sits."""

    def __init__(self, content):
        self.content = content


class FakeClient:
    """Stands in for a client, serving prepared table rows."""

    def __init__(self, spells, content=None, **tables):
        self._spells = spells
        self._tables = tables
        self.install = FakeInstall(content or Path("/nonexistent"))

    def table(self, name, _schema):
        return self._tables.get(name, [])

    def dbc(self, _name):
        rows = self._spells

        class Cursor:
            def rows(self, _schema):
                return iter(rows)

        return Cursor()

    def provider(self, _path):
        return "patch-D.MPQ"


def spell(id_, name, *, rank="", description="", visual=0, icon=0):
    return {"id": id_, "name": name, "rank": rank, "description": description,
            "spell_visual": [visual, 0], "spell_icon_id": icon}


def client_with(spells, content=None, **tables):
    base = {
        "SpellVisual": [], "SpellVisualKit": [], "SpellVisualEffectName": [],
        "SpellIcon": [], "SoundEntries": [],
    }
    return FakeClient(spells, content=content, **{**base, **tables})


def visual_row(id_, cast_kit=0):
    row = {"id": id_, "has_missile": 0, "missile_model": 0, "missile_sound": 0,
           "precast_kit": 0, "cast_kit": cast_kit, "impact_kit": 0, "state_kit": 0,
           "state_done_kit": 0, "channel_kit": 0, "caster_impact_kit": 0,
           "target_impact_kit": 0, "missile_targeting_kit": 0, "instant_area_kit": 0,
           "impact_area_kit": 0, "persistent_area_kit": 0}
    return row


def kit_row(id_, effect=0, sound=0):
    return {"id": id_, "anim_id": 0, "sound_id": sound, "special_effect": [0, 0, 0],
            "head_effect": 0, "chest_effect": 0, "base_effect": effect,
            "left_hand_effect": 0, "right_hand_effect": 0, "breath_effect": 0,
            "left_weapon_effect": 0, "right_weapon_effect": 0, "world_effect": 0}


def test_named_spells_are_stored_and_unnamed_ones_skipped(tmp_path):
    path = tmp_path / "book.sqlite"
    stats = build(client_with([
        spell(1, "Fireball"), spell(2, "   "), spell(3, "Frostbolt"),
    ]), path)

    assert (stats.total, stats.named) == (3, 2)
    db = connect(path)
    assert [r["name"] for r in search(db, "bolt")] == ["Frostbolt"]
    assert fetch(db, 2) is None


def test_a_spell_that_draws_something_keeps_its_resolved_cast(tmp_path):
    path = tmp_path / "book.sqlite"
    stats = build(client_with(
        [spell(7, "Bolt", visual=10)],
        SpellVisual=[visual_row(10, cast_kit=20)],
        SpellVisualKit=[kit_row(20, effect=30)],
        SpellVisualEffectName=[{"id": 30, "name": "fx", "file_name": "spells\\bolt.m2"}],
    ), path)

    assert stats.with_effects == 1
    record = fetch(connect(path), 7)
    assert record["effects"]["models"] == ["spells\\bolt.m2"]
    assert [k["slot"] for k in record["effects"]["kits"]] == ["cast"]


def test_a_spell_that_draws_nothing_stores_no_cast(tmp_path):
    path = tmp_path / "book.sqlite"
    build(client_with([spell(8, "Passive Thing")]), path)
    assert fetch(connect(path), 8)["effects"] is None


def test_search_puts_an_exact_name_first(tmp_path):
    path = tmp_path / "book.sqlite"
    build(client_with([
        spell(1, "Greater Fireball"), spell(2, "Fireball"), spell(3, "Fireball Rank 2"),
    ]), path)
    assert search(connect(path), "Fireball")[0]["name"] == "Fireball"


def test_search_by_id_finds_the_exact_spell_first(tmp_path):
    path = tmp_path / "book.sqlite"
    build(client_with([spell(133, "Fireball"), spell(1337, "Other")]), path)
    assert search(connect(path), "133")[0]["id"] == 133


def test_ties_on_name_prefer_the_one_that_draws_something(tmp_path):
    # 932 rows in the real client are called "Sample Persistent AoE"; the one worth
    # showing is whichever actually has a visual.
    path = tmp_path / "book.sqlite"
    build(client_with(
        [spell(1, "Sample"), spell(2, "Sample", visual=10)],
        SpellVisual=[visual_row(10, cast_kit=20)],
        SpellVisualKit=[kit_row(20, effect=30)],
        SpellVisualEffectName=[{"id": 30, "name": "fx", "file_name": "a.m2"}],
    ), path)
    assert search(connect(path), "Sample")[0]["id"] == 2


def test_an_empty_query_matches_nothing(tmp_path):
    path = tmp_path / "book.sqlite"
    build(client_with([spell(1, "Fireball")]), path)
    assert search(connect(path), "   ") == []


def test_wildcards_in_a_query_are_taken_literally(tmp_path):
    path = tmp_path / "book.sqlite"
    build(client_with([
        spell(1, "Fireball"), spell(2, "Frost"), spell(3, "Reduces damage by 50%"),
    ]), path)
    db = connect(path)
    # Unescaped, "%" would match every row; stripped, it would do the same.
    assert [r["id"] for r in search(db, "%")] == [3]
    assert [r["id"] for r in search(db, "50%")] == [3]
    # And "_" is a single-character wildcard in LIKE.
    assert search(db, "F_reball") == []


def test_the_book_records_how_it_was_built(tmp_path):
    path = tmp_path / "book.sqlite"
    build(client_with([spell(1, "Fireball")]), path)
    meta = dict(sqlite3.connect(path).execute("SELECT key, value FROM meta"))
    assert meta["schema_version"] == str(SCHEMA_VERSION)
    assert meta["spell_source"] == "patch-D.MPQ"


def test_building_replaces_an_existing_book(tmp_path):
    path = tmp_path / "book.sqlite"
    build(client_with([spell(1, "Old")]), path)
    build(client_with([spell(2, "New")]), path)
    db = connect(path)
    assert fetch(db, 1) is None
    assert fetch(db, 2)["name"] == "New"


def test_the_connection_is_read_only(tmp_path):
    path = tmp_path / "book.sqlite"
    build(client_with([spell(1, "Fireball")]), path)
    with pytest.raises(sqlite3.OperationalError):
        connect(path).execute("DELETE FROM spells")


# --- class attribution ------------------------------------------------------------


def advancement(root, entries):
    """Ascension's own class catalogue, as it ships beside the archives."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "CharacterAdvancementData.json").write_text(
        json.dumps(entries), encoding="utf-8")
    return root


def test_a_spell_a_class_grants_records_who_grants_it(tmp_path):
    content = advancement(tmp_path / "content", [
        {"Name": "Blizzard", "Class": "Mage", "Tab": "Frost", "Type": "Ability",
         "RequiredLevel": 20, "Spells": [10]},
    ])
    path = tmp_path / "book.sqlite"
    stats = build(client_with([spell(10, "Blizzard")], content=content), path)

    assert stats.with_owner == 1
    owners = fetch(connect(path), 10)["owners"]
    assert owners == [{"name": "Blizzard", "class": "Mage", "tab": "Frost",
                       "type": "Ability", "level": 20}]


def test_a_spell_granted_twice_keeps_both_ways(tmp_path):
    # The same effect is often a class ability and again a talent that upgrades it;
    # collapsing that would hide exactly the distinction worth seeing.
    content = advancement(tmp_path / "content", [
        {"Name": "Arm of Thorim", "Class": "Stormbringer", "Tab": "Lightning",
         "Type": "Ability", "Spells": [801847]},
        {"Name": "Arm of Thorim", "Class": "Stormbringer", "Tab": "Lightning",
         "Type": "Talent", "Spells": [801847]},
    ])
    path = tmp_path / "book.sqlite"
    build(client_with([spell(801847, "Arm of Thorim")], content=content), path)
    assert [o["type"] for o in fetch(connect(path), 801847)["owners"]] == [
        "Ability", "Talent",
    ]


def test_spells_no_class_grants_have_no_owner(tmp_path):
    content = advancement(tmp_path / "content", [])
    path = tmp_path / "book.sqlite"
    stats = build(client_with([spell(1, "Internal Thing")], content=content), path)
    assert stats.with_owner == 0
    assert fetch(connect(path), 1)["owners"] == []


def test_search_puts_a_spell_a_class_grants_first(tmp_path):
    content = advancement(tmp_path / "content", [
        {"Name": "Blizzard", "Class": "Mage", "Tab": "Frost", "Type": "Ability",
         "Spells": [10]},
    ])
    path = tmp_path / "book.sqlite"
    build(client_with([spell(254633, "Blizzard"), spell(10, "Blizzard")],
                      content=content), path)
    assert search(connect(path), "Blizzard")[0]["id"] == 10


def test_a_missing_advancement_file_is_not_an_error(tmp_path):
    path = tmp_path / "book.sqlite"
    stats = build(client_with([spell(1, "Fireball")], content=tmp_path / "gone"), path)
    assert stats.with_owner == 0
