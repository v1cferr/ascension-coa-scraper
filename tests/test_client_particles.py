"""Reading a particle emitter far enough to replay it."""

from __future__ import annotations

import struct

import pytest

from ascension_coa_scraper.client.particles import (
    Emitter,
    ParticleError,
    read_emitters,
)

_STRIDE = 476
_BODY = 0x200  # where the synthetic file's data blocks begin


def build_m2(emitters: list[dict] | None = None) -> bytes:
    """A WotLK M2 header carrying whole particle emitter records.

    Each entry may set any of the record's fields; anything left out stays zero, which
    is what an emitter that does not use a feature looks like in the client's files.
    """
    emitters = emitters or []
    header = bytearray(0x200)
    header[0:4] = b"MD20"
    struct.pack_into("<I", header, 0x04, 264)

    records = bytearray()
    blocks = bytearray()

    def stash(payload: bytes) -> int:
        """Put a block after the records and return where it will land."""
        at = _BODY + len(emitters) * _STRIDE + len(blocks)
        blocks.extend(payload)
        return at

    def track(values: tuple[float, ...]) -> bytes:
        """An M2Track: two hops from the record to the numbers."""
        if not values:
            return struct.pack("<HHIIII", 0, 0xFFFF, 0, 0, 0, 0)
        inner = stash(struct.pack(f"<{len(values)}f", *values))
        outer = stash(struct.pack("<II", len(values), inner))
        return struct.pack("<HHIIII", 0, 0xFFFF, 0, 0, 1, outer)

    def keys(times: tuple[int, ...], payload: bytes, count: int) -> bytes:
        """A (timestamps, values) pair, as the colour/alpha/scale blocks are stored."""
        if not times:
            return struct.pack("<IIII", 0, 0, 0, 0)
        t_at = stash(struct.pack(f"<{len(times)}H", *times))
        v_at = stash(payload)
        return struct.pack("<IIII", len(times), t_at, count, v_at)

    for spec in emitters:
        rec = bytearray(_STRIDE)
        struct.pack_into("<fff", rec, 0x08, *spec.get("position", (0.0, 0.0, 0.0)))
        struct.pack_into("<I", rec, 0x04, spec.get("flags", 0))
        struct.pack_into("<H", rec, 0x14, spec.get("bone", 0))
        struct.pack_into("<H", rec, 0x16, spec.get("texture", 0))
        struct.pack_into("<BB", rec, 0x28, spec.get("blend", 3), spec.get("kind", 1))
        struct.pack_into("<H", rec, 0x2E, spec.get("tile_rotation", 0))
        struct.pack_into("<HH", rec, 0x30, spec.get("rows", 1), spec.get("cols", 1))

        for name, offset in (
            ("speed", 0x34), ("speed_variation", 0x48), ("vertical_range", 0x5C),
            ("horizontal_range", 0x70), ("gravity", 0x84), ("lifespan", 0x98),
            ("emission_rate", 0xB0), ("area_length", 0xC8), ("area_width", 0xDC),
            ("z_source", 0xF0),
        ):
            value = spec.get(name)
            rec[offset : offset + 20] = track(() if value is None else (value,))

        struct.pack_into("<f", rec, 0xAC, spec.get("lifespan_variation", 0.0))
        struct.pack_into("<f", rec, 0xC4, spec.get("emission_rate_variation", 0.0))

        colors = spec.get("colors", ())
        rec[0x104:0x114] = keys(
            tuple(t for t, _ in colors),
            b"".join(struct.pack("<fff", *c) for _, c in colors),
            len(colors),
        )
        alphas = spec.get("alphas", ())
        rec[0x114:0x124] = keys(
            tuple(t for t, _ in alphas),
            b"".join(struct.pack("<H", a) for _, a in alphas),
            len(alphas),
        )
        scales = spec.get("scales", ())
        rec[0x124:0x134] = keys(
            tuple(t for t, _ in scales),
            b"".join(struct.pack("<ff", *s) for _, s in scales),
            len(scales),
        )
        cells = spec.get("head_cells", ())
        rec[0x13C:0x14C] = keys(
            tuple(t for t, _ in cells),
            b"".join(struct.pack("<H", c) for _, c in cells),
            len(cells),
        )
        records.extend(rec)

    struct.pack_into("<II", header, 0x128, len(emitters), _BODY)
    return bytes(header) + bytes(records) + bytes(blocks)


# --- what is and is not a model ----------------------------------------------------


def test_bytes_that_are_not_an_m2_are_refused():
    with pytest.raises(ParticleError):
        read_emitters(b"not a model at all, not even close")


def test_a_model_with_no_emitters_is_not_an_error():
    # Most of the client's models have none; that is data, not a failure.
    assert read_emitters(build_m2([])) == []


# --- the fixed head ----------------------------------------------------------------


def test_the_head_is_read_back_as_written():
    (emitter,) = read_emitters(build_m2([{
        "position": (1.5, -2.0, 0.25), "bone": 7, "texture": 3,
        "blend": 3, "kind": 2,
    }]))
    assert emitter.position == pytest.approx((1.5, -2.0, 0.25))
    assert emitter.bone == 7
    assert emitter.texture == 3
    assert emitter.blend == "additive"
    assert emitter.kind == "sphere"


def test_an_unknown_blend_is_named_rather_than_dropped():
    # A mode this reader does not have a word for is still worth reporting.
    (emitter,) = read_emitters(build_m2([{"blend": 200}]))
    assert emitter.blend == "mode 200"


# --- the sprite sheet --------------------------------------------------------------


def test_a_single_tile_sheet_is_not_an_animation():
    (emitter,) = read_emitters(build_m2([{"rows": 1, "cols": 1}]))
    assert emitter.tiles == 1
    assert not emitter.is_animated_sprite


def test_a_grid_counts_its_frames():
    (emitter,) = read_emitters(build_m2([{"rows": 2, "cols": 4}]))
    assert emitter.tiles == 8
    assert emitter.is_animated_sprite


def test_a_zero_dimension_is_read_as_one():
    # A grid is never zero-wide; treating it as one keeps a divide from exploding.
    (emitter,) = read_emitters(build_m2([{"rows": 0, "cols": 0}]))
    assert emitter.tiles == 1


# --- motion ------------------------------------------------------------------------


def test_the_motion_tracks_resolve_to_their_values():
    (emitter,) = read_emitters(build_m2([{
        "speed": 12.5, "gravity": -9.8, "lifespan": 0.75,
        "emission_rate": 40.0, "area_length": 2.0, "z_source": 1.25,
    }]))
    assert emitter.speed == pytest.approx(12.5)
    assert emitter.gravity == pytest.approx(-9.8)
    assert emitter.lifespan == pytest.approx(0.75)
    assert emitter.emission_rate == pytest.approx(40.0)
    assert emitter.area_length == pytest.approx(2.0)
    assert emitter.z_source == pytest.approx(1.25)


def test_the_loose_variation_floats_sit_in_the_gaps_between_tracks():
    # The +4 breaks in the 20-byte stride are what these two occupy.
    (emitter,) = read_emitters(build_m2([{
        "lifespan_variation": 0.3, "emission_rate_variation": 5.0,
    }]))
    assert emitter.lifespan_variation == pytest.approx(0.3)
    assert emitter.emission_rate_variation == pytest.approx(5.0)


def test_an_empty_track_reports_nothing_rather_than_a_default():
    # An invented gravity looks exactly like a real one, which is the danger.
    (emitter,) = read_emitters(build_m2([{"speed": 1.0}]))
    assert emitter.gravity is None
    assert emitter.lifespan is None
    assert not emitter.resolved


def test_resolved_means_the_three_that_decide_replay_are_known():
    (emitter,) = read_emitters(build_m2([{
        "speed": 1.0, "lifespan": 0.5, "emission_rate": 10.0,
    }]))
    assert emitter.resolved


# --- appearance over one particle's life -------------------------------------------


def test_colour_keys_are_placed_across_a_normalised_life():
    # Timestamps are absolute milliseconds; what a renderer needs is where each key
    # falls between birth and death.
    (emitter,) = read_emitters(build_m2([{"colors": [
        (0, (1.0, 0.0, 0.0)), (500, (0.0, 1.0, 0.0)), (1000, (0.0, 0.0, 1.0)),
    ]}]))
    assert [t for t, _ in emitter.colors] == pytest.approx([0.0, 0.5, 1.0])
    assert emitter.colors[1][1] == pytest.approx((0.0, 1.0, 0.0))


def test_alpha_is_read_as_a_fixed_point_fraction():
    # Stored as 16-bit fixed point, not a float: 32767 is fully opaque.
    (emitter,) = read_emitters(build_m2([{"alphas": [(0, 32767), (100, 0)]}]))
    assert emitter.alphas[0][1] == pytest.approx(1.0, abs=1e-4)
    assert emitter.alphas[1][1] == pytest.approx(0.0)


def test_scale_keys_carry_a_size_pair():
    (emitter,) = read_emitters(build_m2([{"scales": [(0, (0.5, 0.5)), (100, (2.0, 3.0))]}]))
    assert emitter.scales[-1][1] == pytest.approx((2.0, 3.0))


def test_a_missing_key_block_is_empty_not_invented():
    (emitter,) = read_emitters(build_m2([{}]))
    assert emitter.colors == []
    assert emitter.alphas == []
    assert emitter.scales == []


# --- several emitters --------------------------------------------------------------


def test_every_emitter_is_read_and_keeps_its_index():
    found = read_emitters(build_m2([
        {"speed": 1.0}, {"speed": 2.0}, {"speed": 3.0},
    ]))
    assert [e.index for e in found] == [0, 1, 2]
    assert [e.speed for e in found] == pytest.approx([1.0, 2.0, 3.0])


def test_a_count_that_overruns_the_file_yields_nothing():
    # A truncated download should not be read as though the records were there.
    data = bytearray(build_m2([{"speed": 1.0}]))
    struct.pack_into("<II", data, 0x128, 9999, _BODY)
    assert read_emitters(bytes(data)) == []


# --- gravity that is packed rather than stored as a float ---------------------------

_PACKED = 0x800000


def test_packed_gravity_of_all_zeroes_is_simply_no_gravity():
    # Zero unpacks to zero whichever way the bytes are read, so this one is knowable.
    (emitter,) = read_emitters(build_m2([{"flags": _PACKED, "gravity": 0.0}]))
    assert emitter.gravity == 0.0


def test_packed_gravity_carrying_a_value_is_left_unresolved():
    # The direction is fixed-point over 32767 but the magnitude's scale is not in the
    # file, and a guessed divisor would read as the client's own number. Better nothing.
    (emitter,) = read_emitters(build_m2([{"flags": _PACKED, "gravity": 1.5}]))
    assert emitter.gravity is None


def test_gravity_without_the_flag_is_still_read_as_a_float():
    (emitter,) = read_emitters(build_m2([{"gravity": -9.8}]))
    assert emitter.gravity == pytest.approx(-9.8)


# --- the sprite cell across a life -------------------------------------------------


def test_the_cell_track_is_placed_across_a_normalised_life():
    (emitter,) = read_emitters(build_m2([{
        "rows": 2, "cols": 2, "head_cells": [(0, 0), (50, 1), (100, 3)],
    }]))
    assert [t for t, _ in emitter.head_cells] == pytest.approx([0.0, 0.5, 1.0])
    assert [c for _, c in emitter.head_cells] == [0, 1, 3]


def test_a_cell_beyond_the_sheet_is_clamped_not_dropped():
    # 15% of the client's cell indices overrun their own grid. A cell that overruns is
    # still a cell, and the last one beats showing nothing.
    (emitter,) = read_emitters(build_m2([{
        "rows": 1, "cols": 2, "head_cells": [(0, 9)],
    }]))
    assert emitter.head_cells == [(0.0, 1)]


def test_no_cell_track_is_empty_so_the_renderer_can_hold_one_frame():
    (emitter,) = read_emitters(build_m2([{"rows": 2, "cols": 2}]))
    assert emitter.head_cells == []


def test_tile_rotation_is_read_and_is_not_part_of_the_grid():
    # It takes 3 and 5 as readily as 4, which is how it was told apart from the grid.
    (emitter,) = read_emitters(build_m2([{"tile_rotation": 5, "rows": 2, "cols": 4}]))
    assert emitter.tile_rotation == 5
    assert emitter.tiles == 8
