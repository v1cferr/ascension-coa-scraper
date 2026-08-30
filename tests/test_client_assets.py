"""Resolving a model reference into the files needed to open it."""

from __future__ import annotations

import struct

import pytest

from ascension_coa_scraper.client.assets import (
    M2Error,
    expand,
    parse_textures,
    resolve_path,
)


def build_m2(views: int = 1, textures: tuple[tuple[int, str], ...] = ()) -> bytes:
    """A WotLK M2 header carrying a texture block, padded to a valid size."""
    header = bytearray(0x100)
    header[0:4] = b"MD20"
    struct.pack_into("<I", header, 0x04, 264)
    struct.pack_into("<I", header, 0x44, views)

    names = bytearray()
    records = bytearray()
    name_base = 0x100 + len(textures) * 16
    for kind, name in textures:
        encoded = name.encode("latin-1") + b"\0"
        records += struct.pack("<IIII", kind, 0, len(encoded), name_base + len(names))
        names += encoded
    struct.pack_into("<II", header, 0x50, len(textures), 0x100)
    return bytes(header) + bytes(records) + bytes(names)


def make_exists(*present: str):
    have = {p.lower() for p in present}
    return lambda path: path.lower() in have


# --- resolve_path -----------------------------------------------------------------


def test_a_path_that_exists_is_returned_unchanged():
    assert resolve_path("Spells\\Bolt.m2", make_exists("spells\\bolt.m2")) == "Spells\\Bolt.m2"


def test_mdx_falls_back_to_m2_the_way_the_client_swaps_it():
    # The tables name Warcraft III extensions for models stored as .m2.
    assert resolve_path("Spells\\Lightning.mdx", make_exists("spells\\lightning.m2")) \
        == "Spells\\Lightning.m2"


def test_m2_falls_back_to_mdx():
    assert resolve_path("Spells\\Old.m2", make_exists("spells\\old.mdx")) == "Spells\\Old.mdx"


def test_forward_slashes_are_normalised_to_the_archive_separator():
    assert resolve_path("Spells/Bolt.m2", make_exists("spells\\bolt.m2")) == "Spells\\Bolt.m2"


def test_a_path_present_under_neither_extension_resolves_to_none():
    assert resolve_path("Spells\\Gone.mdx", make_exists()) is None


# --- parse_textures ---------------------------------------------------------------


def test_reads_view_count_and_hardcoded_texture_names():
    data = build_m2(views=3, textures=((0, "spells\\fire.blp"), (0, "spells\\smoke.blp")))
    assert parse_textures(data) == (3, ["spells\\fire.blp", "spells\\smoke.blp"])


def test_runtime_supplied_textures_are_skipped():
    # Type != 0 means the game provides the texture (character skin, hair, item);
    # there is no file to extract.
    data = build_m2(textures=((0, "spells\\real.blp"), (1, "ignored.blp"), (11, "also.blp")))
    assert parse_textures(data)[1] == ["spells\\real.blp"]


def test_texture_names_use_the_archive_separator():
    assert parse_textures(build_m2(textures=((0, "spells/fire.blp"),)))[1] == ["spells\\fire.blp"]


def test_a_model_with_no_textures_is_not_an_error():
    assert parse_textures(build_m2(views=2)) == (2, [])


def test_non_m2_bytes_are_rejected():
    with pytest.raises(M2Error, match="not a WotLK M2"):
        parse_textures(b"BLP2" + bytes(0x100))


def test_a_texture_record_past_the_end_is_reported():
    data = bytearray(build_m2())
    struct.pack_into("<II", data, 0x50, 4, 0xFFFF)
    with pytest.raises(M2Error, match="runs past the end"):
        parse_textures(bytes(data))


def test_a_texture_name_past_the_end_is_reported():
    data = bytearray(build_m2(textures=((0, "a.blp"),)))
    struct.pack_into("<I", data, 0x100 + 12, 0xFFFF)   # ofsFilename
    with pytest.raises(M2Error, match="runs past the end"):
        parse_textures(bytes(data))


# --- expand -----------------------------------------------------------------------


def test_expand_collects_the_model_its_skins_and_its_textures():
    model = build_m2(views=2, textures=((0, "spells\\fire.blp"),))
    exists = make_exists(
        "spells\\bolt.m2", "spells\\bolt00.skin", "spells\\bolt01.skin", "spells\\fire.blp",
    )
    files = expand("Spells\\Bolt.mdx", exists, lambda _p: model)

    assert files.requested == "Spells\\Bolt.mdx"
    assert files.model == "Spells\\Bolt.m2"
    assert files.skins == ["Spells\\Bolt00.skin", "Spells\\Bolt01.skin"]
    assert files.textures == ["spells\\fire.blp"]
    assert files.all_paths[0] == "Spells\\Bolt.m2"


def test_skins_the_archives_do_not_have_are_left_out():
    model = build_m2(views=4)
    exists = make_exists("spells\\bolt.m2", "spells\\bolt00.skin", "spells\\bolt02.skin")
    assert expand("Spells\\Bolt.m2", exists, lambda _p: model).skins == [
        "Spells\\Bolt00.skin", "Spells\\Bolt02.skin",
    ]


def test_textures_the_archives_do_not_have_are_left_out():
    model = build_m2(textures=((0, "there.blp"), (0, "gone.blp")))
    exists = make_exists("spells\\bolt.m2", "there.blp")
    assert expand("Spells\\Bolt.m2", exists, lambda _p: model).textures == ["there.blp"]


def test_an_unreadable_header_still_yields_the_model_itself():
    # Half an asset beats none, and the empty companion lists say what happened.
    exists = make_exists("spells\\bolt.m2")
    files = expand("Spells\\Bolt.m2", exists, lambda _p: b"junk")
    assert files.model == "Spells\\Bolt.m2"
    assert files.skins == [] and files.textures == []


def test_an_unresolvable_model_yields_no_paths_at_all():
    files = expand("Spells\\Gone.mdx", make_exists(), lambda _p: b"")
    assert files.model is None and files.all_paths == []
