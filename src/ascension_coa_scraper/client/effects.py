"""Resolve what a spell actually looks and sounds like.

The client answers that across five tables, none of which names a spell::

    Spell.spell_visual[0]
      -> SpellVisual            one row per visual, with a kit id per moment
                                (precast, cast, impact, channel, state, area, ...)
      -> SpellVisualKit         one row per moment, with an effect id per attachment
                                (hand, chest, head, weapon, world, ...) and a sound id
      -> SpellVisualEffectName  the model file for an effect id
      -> SoundEntries           the sound files for a sound id

`resolve` walks that chain and returns the flattened answer: for one spell, which
model files play at which moment on which attachment, and which sound files go with
them. That is the form a mod author needs -- the per-table rows say nothing on their own.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from . import schema
from .reader import Client

__all__ = ["SpellEffects", "KitEffects", "Sound", "EffectResolver"]

#: SpellVisual columns that point at a SpellVisualKit, and the moment each represents.
KIT_SLOTS = (
    ("precast", "precast_kit"),
    ("cast", "cast_kit"),
    ("impact", "impact_kit"),
    ("state", "state_kit"),
    ("state_done", "state_done_kit"),
    ("channel", "channel_kit"),
    ("caster_impact", "caster_impact_kit"),
    ("target_impact", "target_impact_kit"),
    ("missile_targeting", "missile_targeting_kit"),
    ("instant_area", "instant_area_kit"),
    ("impact_area", "impact_area_kit"),
    ("persistent_area", "persistent_area_kit"),
)

#: SpellVisualKit columns that point at a SpellVisualEffectName, by attachment point.
EFFECT_SLOTS = (
    "head_effect", "chest_effect", "base_effect",
    "left_hand_effect", "right_hand_effect", "breath_effect",
    "left_weapon_effect", "right_weapon_effect", "world_effect",
)


@dataclass(frozen=True)
class Sound:
    """One SoundEntries row, flattened to the files it can play."""

    id: int
    name: str
    directory: str
    files: tuple[str, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        """Full in-archive paths, which is what an extractor needs."""
        base = self.directory.rstrip("\\/")
        return tuple(f"{base}\\{f}" if base else f for f in self.files)


@dataclass
class KitEffects:
    """One moment of a spell's visual: the models and sound it triggers."""

    slot: str
    kit_id: int
    anim_id: int | None = None
    models: dict[str, str] = field(default_factory=dict)   # attachment -> model path
    sound: Sound | None = None

    @property
    def is_empty(self) -> bool:
        return not self.models and self.sound is None


@dataclass
class SpellEffects:
    """Everything the client would play for one spell."""

    spell_id: int
    name: str
    rank: str = ""
    icon: str | None = None
    visual_id: int = 0
    kits: list[KitEffects] = field(default_factory=list)
    missile_model: str | None = None
    missile_sound: Sound | None = None

    def model_paths(self) -> list[str]:
        """Every distinct model file this spell references, in a stable order."""
        seen: dict[str, None] = {}
        for kit in self.kits:
            for path in kit.models.values():
                seen.setdefault(path, None)
        if self.missile_model:
            seen.setdefault(self.missile_model, None)
        return list(seen)

    def sound_paths(self) -> list[str]:
        seen: dict[str, None] = {}
        for kit in self.kits:
            if kit.sound:
                for path in kit.sound.paths:
                    seen.setdefault(path, None)
        if self.missile_sound:
            for path in self.missile_sound.paths:
                seen.setdefault(path, None)
        return list(seen)


class EffectResolver:
    """Loads the five tables once, then answers per-spell queries.

    Loading is eager because every query touches every table, and the tables are small
    next to the archives holding them -- 18,742 effect names and 45,870 sound entries
    on this client.
    """

    def __init__(self, client: Client) -> None:
        self.client = client
        self.visuals = {r["id"]: r for r in client.table("SpellVisual", schema.SPELL_VISUAL)}
        self.kits = {r["id"]: r for r in client.table("SpellVisualKit", schema.SPELL_VISUAL_KIT)}
        self.effect_names = {
            r["id"]: r for r in client.table(
                "SpellVisualEffectName", schema.SPELL_VISUAL_EFFECT_NAME
            )
        }
        self.icons = {
            r["id"]: r["texture_filename"]
            for r in client.table("SpellIcon", schema.SPELL_ICON)
        }
        self.sounds = {
            r["id"]: Sound(
                id=r["id"], name=r["name"], directory=r["directory_base"],
                files=tuple(f for f in r["files"] if f),
            )
            for r in client.table("SoundEntries", schema.SOUND_ENTRIES)
        }

    def _model(self, effect_id: int) -> str | None:
        row = self.effect_names.get(effect_id)
        if row is None:
            return None
        return row["file_name"] or None

    def _kit(self, slot: str, kit_id: int) -> KitEffects | None:
        row = self.kits.get(kit_id)
        if row is None:
            return None
        kit = KitEffects(slot=slot, kit_id=kit_id, anim_id=row.get("anim_id"))
        for column in EFFECT_SLOTS:
            model = self._model(row[column])
            if model:
                kit.models[column.removesuffix("_effect")] = model
        for index, effect_id in enumerate(row["special_effect"]):
            model = self._model(effect_id)
            if model:
                kit.models[f"special_{index}"] = model
        kit.sound = self.sounds.get(row["sound_id"])
        return None if kit.is_empty else kit

    def resolve(self, spell_row: dict) -> SpellEffects:
        """Walk the chain for one decoded Spell.dbc row."""
        visual_id = spell_row["spell_visual"][0]
        out = SpellEffects(
            spell_id=spell_row["id"],
            name=spell_row.get("name", ""),
            rank=spell_row.get("rank", ""),
            icon=self.icons.get(spell_row["spell_icon_id"]) or None,
            visual_id=visual_id,
        )
        visual = self.visuals.get(visual_id)
        if visual is None:
            return out
        for slot, column in KIT_SLOTS:
            kit = self._kit(slot, visual[column])
            if kit is not None:
                out.kits.append(kit)
        if visual["has_missile"]:
            out.missile_model = self._model(visual["missile_model"])
            out.missile_sound = self.sounds.get(visual["missile_sound"])
        return out

    def resolve_many(self, spell_rows: Iterable[dict]) -> list[SpellEffects]:
        return [self.resolve(row) for row in spell_rows]
