from datetime import UTC, datetime

import pytest

from ascension_coa_scraper.discovery import RawRealm
from ascension_coa_scraper.icons import SpriteSheet
from ascension_coa_scraper.models import EntryType, NodeShape
from ascension_coa_scraper.normalize import (
    NormalizeError,
    find_class,
    list_classes,
    normalize_class,
    normalize_talent,
    slugify,
    strip_html,
)

# Copied verbatim from the live payload (Stormbringer / Lightning, node 6851).
LIGHTNING_ROD = {
    "x": 1,
    "y": 6,
    "id": 6851,
    "name": "Lightning Rod",
    "flags": 0,
    "group": 0,
    "tabId": 42,
    "aeCost": 0,
    "teCost": 1,
    "classId": 16,
    "spellId": 300609,
    "iconPath": "Interface\\Icons\\inv_rod_enchantedcobalt",
    "nodeType": "SpendCircle",
    "reqTabAE": 0,
    "reqTabTE": 8,
    "spellIds": [300609],
    "entryType": "Talent",
    "isPassive": 0,
    "maxPoints": 1,
    "sortOrder": 0,
    "description": 'Damage dealt by <span style="color: #ffffff">Forked Lightning</span> now has a '
    '<span class="item-number">15</span><span class="item-number">%</span> chance to spread.'
    "<br /><br />Chance increases with Static.",
    "requiredIds": [0, 0, 0],
    "requiredLevel": 0,
    "isStartingNode": 0,
    "connectedNodeIds": [7769, 34674, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "rankDescriptions": [{"rank": 1, "spellId": 300609, "description": "Rank one text."}],
}

SHEET = SpriteSheet(
    url="https://ascension.gg/icon/coa-builder-icon.webp",
    columns=55,
    rows=55,
    cells={"inv_rod_enchantedcobalt": (32, 31), "class-stormbringer": (7, 54)},
)


def _realm() -> RawRealm:
    return RawRealm(
        row_id="9",
        data={
            "id": 40,
            "slug": "voljin",
            "name": "Vol'Jin",
            "schema_version": {"talents": 2},
            "talents": {
                "classes": [
                    {
                        "classId": 16,
                        "className": "Stormbringer",
                        "tabs": [
                            {"tabId": 42, "tabName": "Lightning", "sortOrder": 1},
                            {"tabId": 87, "tabName": "Class", "sortOrder": 0},
                        ],
                    }
                ],
                "entriesByTab": {"16:42": [LIGHTNING_ROD], "16:87": []},
                "essenceByClass": {"16": {"maxTalentEssence": 25, "maxAbilityEssence": 26}},
            },
        },
    )


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<b>Bold</b> text", "Bold text"),
        ("a<br />b", "a\nb"),
        ("a<br>b<BR/>c", "a\nb\nc"),
        ("&amp; &lt;tag&gt; &#39;", "& <tag> '"),
        ("<span>  spaced   out  </span>", "spaced out"),
        ("", ""),
    ],
)
def test_strip_html(html, expected):
    assert strip_html(html) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Vol'Jin Alpha", "voljin-alpha"),
        ("Knight of Xoroth", "knight-of-xoroth"),
        ("Moon Guard", "moon-guard"),
        ("  ", ""),
    ],
)
def test_slugify(value, expected):
    assert slugify(value) == expected


def test_normalize_talent_maps_upstream_fields():
    talent = normalize_talent(LIGHTNING_ROD, SHEET)

    assert talent.id == 6851
    assert talent.slug == "lightning-rod"
    assert talent.entry_type is EntryType.TALENT
    assert talent.node_shape is NodeShape.CIRCLE
    assert talent.costs.talent_essence == 1
    assert talent.requirements.tree_talent_essence == 8
    assert talent.spell_ids == [300609]
    assert talent.max_ranks == 1


def test_normalize_talent_drops_zero_padding_from_id_arrays():
    talent = normalize_talent(LIGHTNING_ROD, SHEET)

    assert talent.connections == [7769, 34674]
    assert talent.requirements.talent_ids == []


def test_normalize_talent_treats_group_zero_as_no_choice_group():
    assert normalize_talent(LIGHTNING_ROD, SHEET).choice_group is None
    assert normalize_talent({**LIGHTNING_ROD, "group": 582933}, SHEET).choice_group == 582933


def test_normalize_talent_keeps_html_and_adds_plain_text():
    talent = normalize_talent(LIGHTNING_ROD, SHEET)

    assert "<span" in talent.description_html
    assert talent.description.startswith("Damage dealt by Forked Lightning now has a 15% chance")
    assert talent.description.endswith("Chance increases with Static.")
    assert "\n" in talent.description


def test_normalize_talent_resolves_the_icon_to_sheet_coordinates():
    icon = normalize_talent(LIGHTNING_ROD, SHEET).icon

    assert icon.key == "inv_rod_enchantedcobalt"
    assert icon.sprite is not None
    assert (icon.sprite.column, icon.sprite.row) == (32, 31)
    assert icon.file is None


def test_normalize_talent_leaves_sprite_null_when_the_sheet_lacks_the_icon():
    talent = normalize_talent({**LIGHTNING_ROD, "iconPath": "Interface\\Icons\\missing"}, SHEET)

    assert talent.icon.key == "missing"
    assert talent.icon.sprite is None


def test_normalize_talent_coerces_non_boolean_starting_node_flag():
    # Upstream stores 127 for at least one node; anything non-zero means "starting".
    assert normalize_talent({**LIGHTNING_ROD, "isStartingNode": 127}, SHEET).is_starting_node


def test_normalize_talent_survives_a_sparse_entry():
    talent = normalize_talent({"id": 1, "name": "X"}, None)

    assert talent.id == 1
    assert talent.node_shape is NodeShape.UNKNOWN
    assert talent.icon.sprite is None
    assert talent.ranks == []


def test_find_class_accepts_name_slug_and_id():
    realm = _realm()

    for wanted in ("Stormbringer", "stormbringer", "16"):
        assert find_class(realm, wanted)["classId"] == 16


def test_find_class_reports_available_classes():
    with pytest.raises(NormalizeError, match="available: stormbringer"):
        find_class(_realm(), "Warlock")


def test_list_classes():
    assert list_classes(_realm()) == [(16, "Stormbringer", "stormbringer")]


def test_normalize_class_builds_trees_in_sort_order():
    dataset = normalize_class(_realm(), "stormbringer", "https://example.test", SHEET)

    assert [t.slug for t in dataset.trees] == ["class", "lightning"]
    assert dataset.trees[0].is_shared is True
    assert dataset.trees[1].is_shared is False
    assert dataset.trees[1].talents[0].name == "Lightning Rod"


def test_normalize_class_fills_class_info_from_payload_and_bundle_metadata():
    info = normalize_class(_realm(), "stormbringer", "https://example.test", SHEET).class_info

    assert (info.id, info.slug) == (16, "stormbringer")
    assert info.max_talent_essence == 25
    assert info.max_ability_essence == 26
    assert info.class_file == "stormbringer"
    assert info.color == "rgb(0, 125, 237)"
    assert info.icon is not None and info.icon.sprite is not None


def test_normalize_class_records_provenance():
    stamp = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    meta = normalize_class(
        _realm(), "stormbringer", "https://example.test/page", SHEET, scraped_at=stamp
    ).meta

    assert meta.source == "https://example.test/page"
    assert meta.builder == "coa"
    assert meta.realm.slug == "voljin"
    assert meta.scraped_at == "2026-08-13T12:00:00+00:00"
    assert meta.upstream_schema_version == {"talents": 2}
    assert meta.content_hash.startswith("sha256:")
    assert (meta.tree_count, meta.talent_count) == (2, 1)


def test_content_hash_ignores_extraction_time():
    early = normalize_class(
        _realm(), "16", "https://example.test", SHEET, scraped_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    later = normalize_class(
        _realm(), "16", "https://example.test", SHEET, scraped_at=datetime(2026, 8, 13, tzinfo=UTC)
    )

    assert early.meta.content_hash == later.meta.content_hash
    assert early.meta.scraped_at != later.meta.scraped_at


def test_content_hash_changes_when_a_talent_changes():
    baseline = normalize_class(_realm(), "16", "https://example.test", SHEET)

    changed = _realm()
    changed.data["talents"]["entriesByTab"]["16:42"][0] = {**LIGHTNING_ROD, "teCost": 2}
    updated = normalize_class(changed, "16", "https://example.test", SHEET)

    assert baseline.meta.content_hash != updated.meta.content_hash
