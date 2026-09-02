"""Deriving browser-showable previews from client assets."""

from __future__ import annotations

import io
import struct

import pytest

from ascension_coa_scraper.preview import (
    PreviewError,
    UnsupportedAsset,
    model_summary,
    safe_asset,
    texture_png,
)

PIL = pytest.importorskip("PIL", reason="preview conversion needs the 'assets' extra")
from PIL import Image  # noqa: E402


def m2(views=1, textures=(), particles=0, ribbons=0, vertices=0, blends=()) -> bytes:
    """A WotLK M2 header wide enough for describe() to read every count."""
    head = bytearray(0x140)
    head[0:4] = b"MD20"
    struct.pack_into("<I", head, 0x04, 264)
    struct.pack_into("<I", head, 0x44, views)

    # Blocks are (count, offset) pairs, and a real model never has one without the
    # other -- the reader treats a count with a null offset as absent, correctly.
    def block(at, count, offset=0x100):
        struct.pack_into("<II", head, at, count, offset if count else 0)

    block(0x3C, vertices)
    block(0x128, particles)
    block(0x120, ribbons)

    body, names = bytearray(), bytearray()
    tex_at = 0x140
    for name in textures:
        raw = name.encode("latin-1") + b"\0"
        body += struct.pack("<IIII", 0, 0, len(raw), tex_at + len(textures) * 16 + len(names))
        names += raw
    struct.pack_into("<II", head, 0x50, len(textures), tex_at)

    blend_at = tex_at + len(body) + len(names)
    blend_bytes = b"".join(struct.pack("<HH", 0, mode) for mode in blends)
    struct.pack_into("<II", head, 0x70, len(blends), blend_at if blends else 0)
    return bytes(head) + bytes(body) + bytes(names) + blend_bytes


def make_blp(path, size=(8, 4)):
    """Pillow writes no BLP, so round-trip a PNG and rename: enough to prove the
    decode path is wired. Real coverage comes from the client's own files."""
    Image.new("RGBA", size, (255, 0, 0, 128)).save(path, format="PNG")


# --- safe_asset -------------------------------------------------------------------


def test_resolves_a_path_inside_the_tree(tmp_path):
    (tmp_path / "spells").mkdir()
    target = tmp_path / "spells" / "bolt.blp"
    target.write_bytes(b"x")
    assert safe_asset(tmp_path, "spells\\bolt.blp") == target.resolve()


def test_backslashes_and_leading_slashes_are_normalised(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b.blp").write_bytes(b"x")
    assert safe_asset(tmp_path, "/a\\b.blp").name == "b.blp"


@pytest.mark.parametrize("escape", ["../secret", "a/../../secret", "/etc/passwd"])
def test_paths_escaping_the_tree_are_refused(tmp_path, escape):
    (tmp_path.parent / "secret").write_text("no", encoding="utf-8")
    with pytest.raises(PreviewError):
        safe_asset(tmp_path, escape)


def test_an_mdx_name_finds_the_m2_on_disk(tmp_path):
    # The tables name roughly a tenth of their models .mdx for files stored as .m2.
    (tmp_path / "spells").mkdir()
    (tmp_path / "spells" / "bolt.m2").write_bytes(b"x")
    assert safe_asset(tmp_path, "spells\\bolt.mdx").name == "bolt.m2"


def test_an_m2_name_finds_the_mdx_on_disk(tmp_path):
    (tmp_path / "old.mdx").write_bytes(b"x")
    assert safe_asset(tmp_path, "old.m2").name == "old.mdx"


def test_the_literal_name_wins_when_both_exist(tmp_path):
    (tmp_path / "both.m2").write_bytes(b"m2")
    (tmp_path / "both.mdx").write_bytes(b"mdx")
    assert safe_asset(tmp_path, "both.mdx").name == "both.mdx"


def test_the_swap_does_not_apply_to_other_extensions(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    with pytest.raises(PreviewError, match="not in the extracted assets"):
        safe_asset(tmp_path, "a.blp")


def test_a_missing_file_is_reported(tmp_path):
    with pytest.raises(PreviewError, match="not in the extracted assets"):
        safe_asset(tmp_path, "gone.blp")


# --- textures ---------------------------------------------------------------------


def test_a_decodable_texture_becomes_a_png_with_alpha(tmp_path):
    source = tmp_path / "t.blp"
    make_blp(source)
    out = texture_png(source)
    assert out[:8] == b"\x89PNG\r\n\x1a\n"
    with Image.open(io.BytesIO(out)) as decoded:
        assert decoded.mode == "RGBA"
        assert decoded.size == (8, 4)


def test_a_texture_the_decoder_cannot_read_is_distinguished_from_a_missing_one(tmp_path):
    # Present but undecodable is a different answer from absent: one says re-extract,
    # the other says the format is beyond the decoder. The routes map them to
    # different statuses, so the types have to differ too.
    bad = tmp_path / "bad.blp"
    bad.write_bytes(b"not an image at all")
    with pytest.raises(UnsupportedAsset, match="cannot decode"):
        texture_png(bad)
    with pytest.raises(PreviewError):                 # still a PreviewError
        texture_png(bad)
    with pytest.raises(PreviewError) as absent:
        safe_asset(tmp_path, "nothere.blp")
    assert not isinstance(absent.value, UnsupportedAsset)


# --- models -----------------------------------------------------------------------


def test_a_model_summary_carries_structure_and_texture_availability(tmp_path):
    (tmp_path / "spells").mkdir()
    make_blp(tmp_path / "spells" / "there.blp")
    model = tmp_path / "fx.m2"
    model.write_bytes(m2(textures=("spells\\there.blp", "spells\\gone.blp"),
                         particles=3, blends=(4,)))

    summary = model_summary(model, assets=tmp_path)
    assert summary["counts"]["particle_emitters"] == 3
    assert summary["blend_modes"] == ["additive"]
    assert summary["glows"] is True
    assert summary["textures"] == [
        {"path": "spells/there.blp", "available": True},
        {"path": "spells\\gone.blp", "available": False},
    ]


def test_a_model_with_no_geometry_is_marked_particle_only(tmp_path):
    model = tmp_path / "fx.m2"
    model.write_bytes(m2(particles=2, vertices=0))
    assert model_summary(model, assets=tmp_path)["is_particle_only"] is True


def test_glow_is_unknown_only_when_the_model_declares_nothing(tmp_path):
    # No render flags and no emitters: there is genuinely nothing to read, and saying
    # "no" would be a claim the data does not support.
    model = tmp_path / "fx.m2"
    model.write_bytes(m2())
    assert model_summary(model, assets=tmp_path)["glows"] is None


def test_bytes_that_are_not_a_model_are_reported(tmp_path):
    bad = tmp_path / "bad.m2"
    bad.write_bytes(b"nope")
    with pytest.raises(UnsupportedAsset, match="cannot read"):
        model_summary(bad, assets=tmp_path)
