"""Collecting a spell's or a class's extracted assets into one download."""

from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path

import pytest

from ascension_coa_scraper.bundle import (
    BundleError,
    collect_class,
    collect_spell,
    write_zip,
)


def m2(views: int = 1, textures: tuple[str, ...] = ()) -> bytes:
    """A WotLK M2 header naming its textures, enough for the reader to walk."""
    header = bytearray(0x100)
    header[0:4] = b"MD20"
    struct.pack_into("<I", header, 0x04, 264)
    struct.pack_into("<I", header, 0x44, views)
    records, names = bytearray(), bytearray()
    base = 0x100 + len(textures) * 16
    for name in textures:
        encoded = name.encode("latin-1") + b"\0"
        records += struct.pack("<IIII", 0, 0, len(encoded), base + len(names))
        names += encoded
    struct.pack_into("<II", header, 0x50, len(textures), 0x100)
    return bytes(header) + bytes(records) + bytes(names)


def make_tree(root: Path, spells: list[dict], *, realm="voljin", cls="stormbringer"):
    effects = root / "client" / "effects" / realm / f"{cls}.json"
    effects.parent.mkdir(parents=True, exist_ok=True)
    effects.write_text(json.dumps({"spell_count": len(spells), "spells": spells}),
                       encoding="utf-8")
    (root / "client" / "assets").mkdir(parents=True, exist_ok=True)
    return root / "client" / "assets"


def put(assets: Path, rel: str, data: bytes = b"x") -> Path:
    path = assets / rel.replace("\\", "/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def spell(spell_id=1, name="Bolt", models=(), sounds=(), icon=None):
    return {"spell_id": spell_id, "name": name, "models": list(models),
            "sounds": list(sounds), "icon": icon}


def test_collects_models_sounds_and_the_icon(tmp_path):
    assets = make_tree(tmp_path, [spell(
        models=["SPELLS\\bolt.m2"], sounds=["Sound\\a.ogg"],
        icon="Interface\\Icons\\spell_fire")])
    put(assets, "SPELLS/bolt.m2", m2())
    put(assets, "Sound/a.ogg")
    put(assets, "Interface/Icons/spell_fire.blp")

    bundle = collect_spell(tmp_path, "voljin", "stormbringer", 1)
    assert set(bundle.files) == {
        "SPELLS/bolt.m2", "Sound/a.ogg", "Interface/Icons/spell_fire.blp",
    }
    assert bundle.missing == []


def test_a_model_brings_its_skin_geometry_and_textures(tmp_path):
    # The dataset names only the model; alone it opens to nothing.
    assets = make_tree(tmp_path, [spell(models=["SPELLS\\bolt.m2"])])
    put(assets, "SPELLS/bolt.m2", m2(views=2, textures=("spells\\fire.blp",)))
    put(assets, "SPELLS/bolt00.skin")
    put(assets, "SPELLS/bolt01.skin")
    put(assets, "spells/fire.blp")

    assert set(collect_spell(tmp_path, "voljin", "stormbringer", 1).files) == {
        "SPELLS/bolt.m2", "SPELLS/bolt00.skin", "SPELLS/bolt01.skin", "spells/fire.blp",
    }


def test_companions_the_tree_does_not_hold_are_simply_absent(tmp_path):
    assets = make_tree(tmp_path, [spell(models=["SPELLS\\bolt.m2"])])
    put(assets, "SPELLS/bolt.m2", m2(views=3, textures=("gone.blp",)))
    put(assets, "SPELLS/bolt00.skin")

    bundle = collect_spell(tmp_path, "voljin", "stormbringer", 1)
    assert set(bundle.files) == {"SPELLS/bolt.m2", "SPELLS/bolt00.skin"}
    assert bundle.missing == []          # only named paths count as missing


def test_an_mdx_reference_resolves_to_the_m2_on_disk(tmp_path):
    assets = make_tree(tmp_path, [spell(models=["Spells\\old.mdx"])])
    put(assets, "Spells/old.m2", m2())
    assert set(collect_spell(tmp_path, "voljin", "stormbringer", 1).files) == {"Spells/old.m2"}


def test_a_reference_with_no_file_is_recorded_as_missing(tmp_path):
    make_tree(tmp_path, [spell(models=["SPELLS\\gone.m2"], sounds=["Sound\\gone.ogg"])])
    bundle = collect_spell(tmp_path, "voljin", "stormbringer", 1)
    assert bundle.files == {}
    assert sorted(bundle.missing) == ["SPELLS\\gone.m2", "Sound\\gone.ogg"]


def test_an_unparsable_model_is_still_bundled_on_its_own(tmp_path):
    assets = make_tree(tmp_path, [spell(models=["SPELLS\\bad.m2"])])
    put(assets, "SPELLS/bad.m2", b"not an m2")
    assert set(collect_spell(tmp_path, "voljin", "stormbringer", 1).files) == {"SPELLS/bad.m2"}


def test_a_class_bundle_deduplicates_across_spells(tmp_path):
    assets = make_tree(tmp_path, [
        spell(1, models=["SPELLS\\shared.m2"]),
        spell(2, models=["SPELLS\\shared.m2", "SPELLS\\own.m2"]),
    ])
    put(assets, "SPELLS/shared.m2", m2())
    put(assets, "SPELLS/own.m2", m2())
    assert set(collect_class(tmp_path, "voljin", "stormbringer").files) == {
        "SPELLS/shared.m2", "SPELLS/own.m2",
    }


def test_the_bundle_name_carries_the_spell(tmp_path):
    assets = make_tree(tmp_path, [spell(801847, name="Arm of Thorim",
                                        models=["SPELLS\\bolt.m2"])])
    put(assets, "SPELLS/bolt.m2", m2())
    bundle = collect_spell(tmp_path, "voljin", "stormbringer", 801847)
    assert bundle.name == "stormbringer-801847-arm-of-thorim"


def test_unknown_class_and_spell_are_reported(tmp_path):
    make_tree(tmp_path, [spell(1)])
    with pytest.raises(BundleError, match="no effects for ghost"):
        collect_spell(tmp_path, "voljin", "ghost", 1)
    with pytest.raises(BundleError, match="spell 99 is not in"):
        collect_spell(tmp_path, "voljin", "stormbringer", 99)


def test_a_missing_asset_tree_says_what_to_run(tmp_path):
    effects = tmp_path / "client" / "effects" / "voljin" / "stormbringer.json"
    effects.parent.mkdir(parents=True)
    effects.write_text(json.dumps({"spells": [spell(1)]}), encoding="utf-8")
    with pytest.raises(BundleError, match="client extract"):
        collect_spell(tmp_path, "voljin", "stormbringer", 1)


def test_the_zip_holds_the_files_under_one_named_folder(tmp_path):
    assets = make_tree(tmp_path, [spell(models=["SPELLS\\bolt.m2"])])
    put(assets, "SPELLS/bolt.m2", m2())
    bundle = collect_spell(tmp_path, "voljin", "stormbringer", 1)

    with zipfile.ZipFile(io.BytesIO(write_zip(bundle))) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == [f"{bundle.name}/SPELLS/bolt.m2"]


def test_the_zip_explains_anything_it_could_not_include(tmp_path):
    make_tree(tmp_path, [spell(sounds=["Sound\\gone.ogg"])])
    (tmp_path / "client" / "assets").mkdir(parents=True, exist_ok=True)
    bundle = collect_spell(tmp_path, "voljin", "stormbringer", 1)

    with zipfile.ZipFile(io.BytesIO(write_zip(bundle))) as archive:
        manifest = archive.read(f"{bundle.name}/MISSING.txt").decode()
    assert "Sound\\gone.ogg" in manifest
    assert "client extract" in manifest
