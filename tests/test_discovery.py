import json

import pytest

from ascension_coa_scraper.discovery import (
    DatasetNotFoundError,
    find_realms,
    select_realm,
)
from ascension_coa_scraper.flight import parse_rows


def _realm(slug: str, realm_id: int) -> dict:
    return {
        "id": realm_id,
        "slug": slug,
        "name": slug.title(),
        "schema_version": {"talents": 2},
        "talents": {
            "meta": {},
            "classes": [{"classId": 16, "className": "Stormbringer", "tabs": []}],
            "entriesByTab": {"16:42": []},
            "essenceByClass": {},
        },
    }


def _rows(*realms: dict):
    # Mirrors the real page: realms live in a prop of an RSC element, several levels deep.
    element = ["$", "$L4d", None, {"value": list(realms), "children": "$L1aa"}]
    return parse_rows(f"9:{json.dumps(element)}\n")


def test_find_realms_locates_payloads_nested_in_rsc_props():
    realms = find_realms(_rows(_realm("voljin-alpha", 39), _realm("voljin", 40)))

    assert [r.slug for r in realms] == ["voljin-alpha", "voljin"]
    assert realms[0].row_id == "9"
    assert realms[0].realm_id == 39
    assert realms[0].name == "Voljin-Alpha"
    assert realms[0].upstream_schema_version == {"talents": 2}
    assert "entriesByTab" in realms[0].talents


def test_find_realms_ignores_objects_missing_the_talents_markers():
    rows = parse_rows(json.dumps({"talents": {"classes": []}}).join(["9:", "\n"]))

    assert find_realms(rows) == []


def test_find_realms_skips_rows_that_are_not_json():
    rows = parse_rows('2:I[339756,["/chunk.js"],"default"]\n')

    assert find_realms(rows) == []


def test_select_realm_defaults_to_the_first_payload():
    realms = find_realms(_rows(_realm("voljin-alpha", 39), _realm("voljin", 40)))

    assert select_realm(realms).slug == "voljin-alpha"


def test_select_realm_matches_by_slug():
    realms = find_realms(_rows(_realm("voljin-alpha", 39), _realm("voljin", 40)))

    assert select_realm(realms, "voljin").realm_id == 40


def test_select_realm_reports_available_slugs_when_missing():
    realms = find_realms(_rows(_realm("voljin", 40)))

    with pytest.raises(DatasetNotFoundError, match="available: voljin"):
        select_realm(realms, "nope")


def test_select_realm_explains_an_empty_page():
    with pytest.raises(DatasetNotFoundError, match="DATA_SOURCE"):
        select_realm([])
