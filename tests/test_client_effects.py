"""Walking Spell -> SpellVisual -> SpellVisualKit -> model/sound.

The resolver is driven through a stand-in for `Client` so the chain can be exercised
with a handful of rows instead of the client's 239,062 spells.
"""

from __future__ import annotations

from ascension_coa_scraper.client.effects import EffectResolver, Sound


class FakeClient:
    """Serves prepared table rows in place of reading archives."""

    def __init__(self, **tables: list[dict]) -> None:
        self._tables = tables

    def table(self, name: str, _schema: object) -> list[dict]:
        return self._tables.get(name, [])


def visual(id_, **overrides):
    row = {
        "id": id_, "has_missile": 0, "missile_model": 0, "missile_sound": 0,
        "precast_kit": 0, "cast_kit": 0, "impact_kit": 0, "state_kit": 0,
        "state_done_kit": 0, "channel_kit": 0, "caster_impact_kit": 0,
        "target_impact_kit": 0, "missile_targeting_kit": 0, "instant_area_kit": 0,
        "impact_area_kit": 0, "persistent_area_kit": 0,
    }
    return row | overrides


def kit(id_, **overrides):
    row = {
        "id": id_, "anim_id": 0, "sound_id": 0, "special_effect": [0, 0, 0],
        "head_effect": 0, "chest_effect": 0, "base_effect": 0,
        "left_hand_effect": 0, "right_hand_effect": 0, "breath_effect": 0,
        "left_weapon_effect": 0, "right_weapon_effect": 0, "world_effect": 0,
    }
    return row | overrides


def effect_name(id_, file_name):
    return {"id": id_, "name": f"fx{id_}", "file_name": file_name}


def sound_entry(id_, name, directory, files):
    return {"id": id_, "name": name, "directory_base": directory,
            "files": list(files) + [""] * (10 - len(files))}


def spell(id_, visual_id, *, name="Test", icon_id=0, rank=""):
    return {"id": id_, "name": name, "rank": rank,
            "spell_visual": [visual_id, 0], "spell_icon_id": icon_id}


def test_resolves_a_cast_kit_to_its_model_and_sound():
    client = FakeClient(
        SpellVisual=[visual(10, cast_kit=20)],
        SpellVisualKit=[kit(20, right_hand_effect=30, sound_id=40)],
        SpellVisualEffectName=[effect_name(30, "Spells\\Fireball_Hand.m2")],
        SoundEntries=[sound_entry(40, "FireCast", "Sound\\Spells", ["FireCast.wav"])],
        SpellIcon=[{"id": 5, "texture_filename": "Interface\\Icons\\Spell_Fire_Flamebolt"}],
    )
    fx = EffectResolver(client).resolve(spell(133, 10, name="Fireball", icon_id=5))

    assert fx.name == "Fireball"
    assert fx.icon == "Interface\\Icons\\Spell_Fire_Flamebolt"
    assert [k.slot for k in fx.kits] == ["cast"]
    assert fx.kits[0].models == {"right_hand": "Spells\\Fireball_Hand.m2"}
    assert fx.model_paths() == ["Spells\\Fireball_Hand.m2"]
    assert fx.sound_paths() == ["Sound\\Spells\\FireCast.wav"]


def test_each_populated_slot_becomes_its_own_kit_in_chain_order():
    client = FakeClient(
        SpellVisual=[visual(10, precast_kit=21, cast_kit=22, impact_kit=23)],
        SpellVisualKit=[
            kit(21, base_effect=31), kit(22, base_effect=32), kit(23, base_effect=33),
        ],
        SpellVisualEffectName=[effect_name(i, f"m{i}.m2") for i in (31, 32, 33)],
    )
    fx = EffectResolver(client).resolve(spell(1, 10))
    assert [k.slot for k in fx.kits] == ["precast", "cast", "impact"]


def test_kits_with_neither_model_nor_sound_are_dropped():
    # A visual referencing an empty kit is common; carrying it would pad every spell
    # with rows that say nothing.
    client = FakeClient(
        SpellVisual=[visual(10, cast_kit=20, impact_kit=21)],
        SpellVisualKit=[kit(20, base_effect=30), kit(21)],
        SpellVisualEffectName=[effect_name(30, "used.m2")],
    )
    fx = EffectResolver(client).resolve(spell(1, 10))
    assert [k.slot for k in fx.kits] == ["cast"]


def test_effect_rows_with_an_empty_file_name_are_not_reported_as_models():
    client = FakeClient(
        SpellVisual=[visual(10, cast_kit=20)],
        SpellVisualKit=[kit(20, base_effect=30, sound_id=40)],
        SpellVisualEffectName=[effect_name(30, "")],
        SoundEntries=[sound_entry(40, "s", "Sound", ["a.wav"])],
    )
    fx = EffectResolver(client).resolve(spell(1, 10))
    assert fx.model_paths() == []
    assert fx.sound_paths() == ["Sound\\a.wav"]


def test_special_effect_array_is_indexed_by_position():
    client = FakeClient(
        SpellVisual=[visual(10, cast_kit=20)],
        SpellVisualKit=[kit(20, special_effect=[31, 0, 33])],
        SpellVisualEffectName=[effect_name(31, "one.m2"), effect_name(33, "three.m2")],
    )
    fx = EffectResolver(client).resolve(spell(1, 10))
    assert fx.kits[0].models == {"special_0": "one.m2", "special_2": "three.m2"}


def test_missile_is_resolved_only_when_the_visual_declares_one():
    tables = dict(
        SpellVisualKit=[],
        SpellVisualEffectName=[effect_name(50, "Spells\\Bolt_Missile.m2")],
        SoundEntries=[sound_entry(60, "Fly", "Sound\\Spells", ["Bolt.ogg"])],
    )
    with_missile = FakeClient(
        SpellVisual=[visual(10, has_missile=1, missile_model=50, missile_sound=60)], **tables
    )
    fx = EffectResolver(with_missile).resolve(spell(1, 10))
    assert fx.missile_model == "Spells\\Bolt_Missile.m2"
    assert fx.sound_paths() == ["Sound\\Spells\\Bolt.ogg"]

    without = FakeClient(
        SpellVisual=[visual(10, has_missile=0, missile_model=50, missile_sound=60)], **tables
    )
    assert EffectResolver(without).resolve(spell(1, 10)).missile_model is None


def test_a_spell_whose_visual_is_absent_resolves_to_an_empty_result():
    client = FakeClient(SpellVisual=[], SpellVisualKit=[])
    fx = EffectResolver(client).resolve(spell(7, 999, name="Passive"))
    assert fx.spell_id == 7 and fx.name == "Passive"
    assert fx.kits == [] and fx.model_paths() == [] and fx.sound_paths() == []


def test_model_paths_are_deduplicated_but_keep_first_seen_order():
    client = FakeClient(
        SpellVisual=[visual(10, precast_kit=20, cast_kit=21)],
        SpellVisualKit=[
            kit(20, left_hand_effect=30, right_hand_effect=30),
            kit(21, base_effect=31),
        ],
        SpellVisualEffectName=[effect_name(30, "hands.m2"), effect_name(31, "base.m2")],
    )
    fx = EffectResolver(client).resolve(spell(1, 10))
    assert fx.model_paths() == ["hands.m2", "base.m2"]


def test_sound_paths_join_the_directory_and_skip_empty_slots():
    sound = Sound(id=1, name="s", directory="Sound\\Spells\\", files=("a.wav", "b.ogg"))
    assert sound.paths == ("Sound\\Spells\\a.wav", "Sound\\Spells\\b.ogg")


def test_sound_without_a_directory_yields_bare_file_names():
    assert Sound(id=1, name="s", directory="", files=("a.wav",)).paths == ("a.wav",)
