"""Column layouts for the client tables this project reads.

These are the stock 3.3.5a layouts. Ascension keeps them: its Spell.dbc holds 239,062
records against Blizzard's 46,583, but still 234 four-byte fields per record. Where a
table is only partly needed, the schema declares the leading columns and sets
``trailing=True`` so a server that appends columns does not invalidate it.

Field positions are load-bearing and easy to get subtly wrong, so `validate.py` checks
decoded rows against values that are independently known.
"""

from __future__ import annotations

from .dbc import FLOAT, INT, LOC, STR, UINT, Column, Table

# --- The visual/sound chain -------------------------------------------------------
#
# Spell.SpellVisual[0] -> SpellVisual.<slot>Kit -> SpellVisualKit.<slot>Effect
#   -> SpellVisualEffectName.FileName   (an .mdx/.m2 model path)
# and SpellVisualKit.SoundID -> SoundEntries.File[]  (the .wav/.mp3/.ogg names)
#
# That is the whole of "which effect and which sound does this spell play", and it is
# why these five tables are the ones extracted first.

SPELL_VISUAL_EFFECT_NAME = Table(
    "SpellVisualEffectName",
    (
        Column("id", UINT),
        Column("name", STR),
        Column("file_name", STR),          # model path, e.g. Spells\\Fireball_Missile.mdx
        Column("area_effect_size", FLOAT),
        Column("scale", FLOAT),
        Column("min_allowed_scale", FLOAT),
        Column("max_allowed_scale", FLOAT),
    ),
    known_widths=(7,),
)

SPELL_VISUAL_KIT = Table(
    "SpellVisualKit",
    (
        Column("id", UINT),
        Column("start_anim_id", INT),
        Column("anim_id", INT),
        Column("head_effect", INT),
        Column("chest_effect", INT),
        Column("base_effect", INT),
        Column("left_hand_effect", INT),
        Column("right_hand_effect", INT),
        Column("breath_effect", INT),
        Column("left_weapon_effect", INT),
        Column("right_weapon_effect", INT),
        Column("special_effect", INT, 3),
        Column("world_effect", INT),
        Column("sound_id", INT),
        Column("shake_id", INT),
        Column("char_proc", INT, 4),
        Column("char_param_zero", FLOAT, 4),
        Column("char_param_one", FLOAT, 4),
        Column("char_param_two", FLOAT, 4),
        Column("char_param_three", FLOAT, 4),
        Column("flags", UINT),
    ),
    trailing=True,
    known_widths=(38,),
)

SPELL_VISUAL = Table(
    "SpellVisual",
    (
        Column("id", UINT),
        Column("precast_kit", INT),
        Column("cast_kit", INT),
        Column("impact_kit", INT),
        Column("state_kit", INT),
        Column("state_done_kit", INT),
        Column("channel_kit", INT),
        Column("has_missile", INT),
        Column("missile_model", INT),
        Column("missile_path_type", INT),
        Column("missile_destination_attachment", INT),
        Column("missile_sound", INT),
        Column("anim_event_sound_id", INT),
        Column("flags", UINT),
        Column("caster_impact_kit", INT),
        Column("target_impact_kit", INT),
        Column("missile_attachment", INT),
        Column("missile_follow_ground_height", INT),
        Column("missile_follow_ground_drop_speed", INT),
        Column("missile_follow_ground_approach", INT),
        Column("missile_follow_ground_flags", INT),
        Column("missile_motion", INT),
        Column("missile_targeting_kit", INT),
        Column("instant_area_kit", INT),
        Column("impact_area_kit", INT),
        Column("persistent_area_kit", INT),
        Column("missile_cast_offset", FLOAT, 3),
        Column("missile_impact_offset", FLOAT, 3),
    ),
    trailing=True,
    known_widths=(32,),
)

SOUND_ENTRIES = Table(
    "SoundEntries",
    (
        Column("id", UINT),
        Column("sound_type", INT),
        Column("name", STR),
        Column("files", STR, 10),
        Column("freq", INT, 10),
        Column("directory_base", STR),      # e.g. Sound\\Spells
        Column("volume", FLOAT),
        Column("flags", UINT),
        Column("min_distance", FLOAT),
        Column("distance_cutoff", FLOAT),
        Column("eax_definition", INT),
        Column("sound_entries_advanced_id", INT),
    ),
    trailing=True,
    known_widths=(30,),
)

SPELL_ICON = Table(
    "SpellIcon",
    (Column("id", UINT), Column("texture_filename", STR)),
    known_widths=(2,),
)

# --- Spell.dbc --------------------------------------------------------------------
#
# 234 fields in 3.3.5a. Only the leading 204 are declared: everything the visual and
# sound chain needs sits at or below field 203, and stopping there keeps the schema
# from having to track columns nothing here reads.

SPELL = Table(
    "Spell",
    (
        Column("id", UINT),
        Column("category", INT),
        Column("dispel_type", INT),
        Column("mechanic", INT),
        Column("attributes", UINT, 8),          # Attributes + AttributesEx..ExG
        Column("stances", UINT),
        Column("unk_320_1", UINT),
        Column("stances_not", UINT),
        Column("unk_320_2", UINT),
        Column("targets", UINT),
        Column("target_creature_type", INT),
        Column("requires_spell_focus", INT),
        Column("facing_caster_flags", INT),
        Column("caster_aura_state", INT),
        Column("target_aura_state", INT),
        Column("caster_aura_state_not", INT),
        Column("target_aura_state_not", INT),
        Column("caster_aura_spell", INT),
        Column("target_aura_spell", INT),
        Column("exclude_caster_aura_spell", INT),
        Column("exclude_target_aura_spell", INT),
        Column("casting_time_index", INT),
        Column("recovery_time", INT),
        Column("category_recovery_time", INT),
        Column("interrupt_flags", UINT),
        Column("aura_interrupt_flags", UINT),
        Column("channel_interrupt_flags", UINT),
        Column("proc_flags", UINT),
        Column("proc_chance", INT),
        Column("proc_charges", INT),
        Column("max_level", INT),
        Column("base_level", INT),
        Column("spell_level", INT),
        Column("duration_index", INT),
        Column("power_type", INT),
        Column("mana_cost", INT),
        Column("mana_cost_per_level", INT),
        Column("mana_per_second", INT),
        Column("mana_per_second_per_level", INT),
        Column("range_index", INT),
        Column("speed", FLOAT),
        Column("modal_next_spell", INT),
        Column("stack_amount", INT),
        Column("totem", INT, 2),
        Column("reagent", INT, 8),
        Column("reagent_count", INT, 8),
        Column("equipped_item_class", INT),
        Column("equipped_item_subclass_mask", INT),
        Column("equipped_item_inventory_type_mask", INT),
        Column("effect", INT, 3),
        Column("effect_die_sides", INT, 3),
        Column("effect_real_points_per_level", FLOAT, 3),
        Column("effect_base_points", INT, 3),
        Column("effect_mechanic", INT, 3),
        Column("effect_implicit_target_a", INT, 3),
        Column("effect_implicit_target_b", INT, 3),
        Column("effect_radius_index", INT, 3),
        Column("effect_apply_aura_name", INT, 3),
        Column("effect_amplitude", INT, 3),
        Column("effect_value_multiplier", FLOAT, 3),
        Column("effect_chain_target", INT, 3),
        Column("effect_item_type", INT, 3),
        Column("effect_misc_value", INT, 3),
        Column("effect_misc_value_b", INT, 3),
        Column("effect_trigger_spell", INT, 3),
        Column("effect_points_per_combo_point", FLOAT, 3),
        Column("effect_spell_class_mask_a", UINT, 3),
        Column("effect_spell_class_mask_b", UINT, 3),
        Column("effect_spell_class_mask_c", UINT, 3),
        Column("spell_visual", INT, 2),         # -> SpellVisual.id
        Column("spell_icon_id", INT),
        Column("active_icon_id", INT),
        Column("spell_priority", INT),
        Column("name", LOC),
        Column("rank", LOC),
        Column("description", LOC),
        Column("tooltip", LOC),
    ),
    trailing=True,
    known_widths=(234,),
)

#: Tables keyed by their DBFilesClient name, for the generic dump command.
TABLES = {
    "Spell": SPELL,
    "SpellVisual": SPELL_VISUAL,
    "SpellVisualKit": SPELL_VISUAL_KIT,
    "SpellVisualEffectName": SPELL_VISUAL_EFFECT_NAME,
    "SpellIcon": SPELL_ICON,
    "SoundEntries": SOUND_ENTRIES,
}
