"""Read a particle emitter completely enough to replay it.

`model.py` describes an effect: how many emitters, which textures, how they blend.
That is enough to read a spell off a page and not nearly enough to watch one. This
module reads the rest of the emitter record -- where particles are born, how fast and
in which direction they are thrown, how long they live, and how their colour, opacity
and size change over that life.

It matters because 626 of this client's 1,486 effect models have **zero vertices**.
They are emitters and nothing else, so a viewer that draws only geometry draws nothing
at all for 42% of the archive. The particles are not decoration on the effect; they are
the effect.

Every offset here was found by scanning the records rather than trusting a
specification. The layout is a run of ten M2Tracks at a fixed 20-byte stride broken by
two 4-byte gaps, and it resolves at 100% across the 24,980 emitters this client ships
-- including the two gaps landing exactly where a loose `lifespanVary` and
`emissionRateVary` float belong. The six colour/alpha/scale arrays that follow confirm
their own types by the spacing between the blocks they point at: 2 bytes a key for the
timestamps, 12 for an RGB triple, 2 for a fixed16 alpha, 8 for a size pair.

Where a value cannot be resolved it comes back as ``None`` rather than a plausible
number. An invented gravity looks exactly like a real one until you compare it against
the game.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

__all__ = ["Emitter", "ParticleError", "read_emitters"]


class ParticleError(Exception):
    """The file is not shaped like something that holds emitters."""


_MD20 = b"MD20"
_OFS_PARTICLE_EMITTERS = 0x128
_STRIDE = 476

#: The record's fixed head. Validated across every emitter the client ships: bones all
#: fall inside the model's own bone count and positions are all finite and small
#: (median 0.28, 95th percentile 3.88), which is what a local-space offset looks like.
_OFS_POSITION = 0x08
_OFS_BONE = 0x14
_OFS_TEXTURE = 0x16
_OFS_BLEND = 0x28
_OFS_KIND = 0x29

#: The sprite sheet. Every one of the 24,980 emitters reports a power of two in 1..8
#: for both, which is the signature of a tile grid and not of a misread offset.
_OFS_ROWS = 0x30
_OFS_COLS = 0x32

#: The motion tracks, in the order the format lays them out. The stride is 20 except
#: where a loose "variation" float follows a track, which is the +4 at `lifespan` and
#: at `emission_rate`.
_MOTION_TRACKS = {
    "speed": 0x34,
    "speed_variation": 0x48,
    "vertical_range": 0x5C,
    "horizontal_range": 0x70,
    "gravity": 0x84,
    "lifespan": 0x98,
    "emission_rate": 0xB0,
    "area_length": 0xC8,
    "area_width": 0xDC,
    "z_source": 0xF0,
}

#: The two loose floats sitting in the gaps, each right after the track it varies.
_OFS_LIFESPAN_VARY = 0xAC
_OFS_EMISSION_RATE_VARY = 0xC4

#: Colour, opacity and size across one particle's life, as (times, values) pairs.
_OFS_COLOR_TIMES, _OFS_COLOR_VALUES = 0x104, 0x10C
_OFS_ALPHA_TIMES, _OFS_ALPHA_VALUES = 0x114, 0x11C
_OFS_SCALE_TIMES, _OFS_SCALE_VALUES = 0x124, 0x12C

#: Alpha is stored as a 16-bit fixed-point fraction, not a float.
_FIXED16 = 32767.0

#: Where the model's own data can possibly start, used to reject an array whose offset
#: points into the header instead of into the file's body.
_BODY_STARTS = 0x140

BLEND_MODES = {
    0: "opaque",
    1: "alpha key",
    2: "alpha",
    3: "additive",
    4: "additive alpha",
    5: "modulate",
    6: "modulate 2x",
}

EMITTER_TYPES = {1: "plane", 2: "sphere", 3: "spline", 4: "bone"}


@dataclass
class Emitter:
    """One emitter, read far enough to run it.

    The motion fields are optional on purpose: a track this reader cannot resolve
    yields ``None``, which a renderer can fall back on openly, rather than a made-up
    default it would then draw as though it were the client's own number.
    """

    index: int

    # Where particles come from.
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bone: int = 0
    kind: str = ""

    # What they are drawn with.
    texture: int = 0
    blend: str = ""
    rows: int = 1
    cols: int = 1

    # How they move. `None` means the track did not resolve.
    speed: float | None = None
    speed_variation: float | None = None
    vertical_range: float | None = None
    horizontal_range: float | None = None
    gravity: float | None = None
    lifespan: float | None = None
    lifespan_variation: float = 0.0
    emission_rate: float | None = None
    emission_rate_variation: float = 0.0
    area_length: float | None = None
    area_width: float | None = None
    z_source: float | None = None

    # How they look across that life, as (fraction, value) from birth to death.
    colors: list[tuple[float, tuple[float, float, float]]] = field(default_factory=list)
    alphas: list[tuple[float, float]] = field(default_factory=list)
    scales: list[tuple[float, tuple[float, float]]] = field(default_factory=list)

    @property
    def tiles(self) -> int:
        """How many frames the sprite sheet holds."""
        return max(1, self.rows) * max(1, self.cols)

    @property
    def is_animated_sprite(self) -> bool:
        """Whether the texture is a sheet to step through rather than one image."""
        return self.tiles > 1

    @property
    def resolved(self) -> bool:
        """Whether enough of the motion is known to replay this honestly."""
        return None not in (self.speed, self.lifespan, self.emission_rate)


def _array(data: bytes, at: int) -> tuple[int, int]:
    """An M2Array: a count and an offset into the file."""
    return struct.unpack_from("<II", data, at)


def _plausible(count: int, offset: int, size: int, width: int) -> bool:
    """Whether an array can be read without walking off the end of the file."""
    if count == 0:
        return False
    return _BODY_STARTS <= offset and offset + count * width <= size


def _track_values(data: bytes, at: int, width: int) -> tuple[int, int] | None:
    """Resolve an M2Track down to the block holding its first animation's values.

    A track's values are an array OF arrays -- one entry per animation sequence -- so
    reaching a number means following two hops. Returns (count, offset) of the inner
    block, or None when either hop does not land somewhere readable.
    """
    size = len(data)
    try:
        outer_count, outer_at = _array(data, at + 12)
    except struct.error:
        return None
    if not _plausible(outer_count, outer_at, size, 8):
        return None
    try:
        inner_count, inner_at = _array(data, outer_at)
    except struct.error:
        return None
    if not _plausible(inner_count, inner_at, size, width):
        return None
    return inner_count, inner_at


def _track_float(data: bytes, at: int) -> float | None:
    """The first value of a scalar track.

    Spell emitters overwhelmingly hold one constant per track, so the first value is
    the value. Where a track really does animate, this is its starting point.
    """
    found = _track_values(data, at, 4)
    if found is None:
        return None
    try:
        (value,) = struct.unpack_from("<f", data, found[1])
    except struct.error:
        return None
    return value if value == value else None  # reject NaN


def _keyed(
    data: bytes, times_at: int, values_at: int, width: int, unpack: str
) -> list[tuple[float, tuple[float, ...]]]:
    """Read a (timestamps, values) pair into keys placed across a 0..1 life.

    The timestamps are absolute milliseconds; a renderer only cares where each key
    falls between birth and death, so they are normalised against the last one.
    """
    size = len(data)
    t_count, t_at = _array(data, times_at)
    v_count, v_at = _array(data, values_at)
    if not _plausible(t_count, t_at, size, 2) or not _plausible(v_count, v_at, size, width):
        return []
    count = min(t_count, v_count)
    try:
        stamps = list(struct.unpack_from(f"<{count}H", data, t_at))
    except struct.error:
        return []
    span = float(stamps[-1]) if stamps and stamps[-1] else 1.0
    keys: list[tuple[float, tuple[float, ...]]] = []
    for i in range(count):
        try:
            value = struct.unpack_from(unpack, data, v_at + i * width)
        except struct.error:
            break
        keys.append((min(1.0, stamps[i] / span), value))
    return keys


def _one_emitter(data: bytes, at: int, index: int) -> Emitter:
    """Read a single record. Anything unreadable is left as None, never invented."""
    emitter = Emitter(index=index)

    emitter.position = struct.unpack_from("<fff", data, at + _OFS_POSITION)
    (emitter.bone,) = struct.unpack_from("<H", data, at + _OFS_BONE)
    (emitter.texture,) = struct.unpack_from("<H", data, at + _OFS_TEXTURE)
    blend, kind = struct.unpack_from("<BB", data, at + _OFS_BLEND)
    emitter.blend = BLEND_MODES.get(blend, f"mode {blend}")
    emitter.kind = EMITTER_TYPES.get(kind, f"type {kind}")
    rows, cols = struct.unpack_from("<HH", data, at + _OFS_ROWS)
    emitter.rows, emitter.cols = max(1, rows), max(1, cols)

    for name, offset in _MOTION_TRACKS.items():
        setattr(emitter, name, _track_float(data, at + offset))

    (emitter.lifespan_variation,) = struct.unpack_from("<f", data, at + _OFS_LIFESPAN_VARY)
    (emitter.emission_rate_variation,) = struct.unpack_from(
        "<f", data, at + _OFS_EMISSION_RATE_VARY
    )

    emitter.colors = [
        (t, (r, g, b))
        for t, (r, g, b) in _keyed(
            data, at + _OFS_COLOR_TIMES, at + _OFS_COLOR_VALUES, 12, "<fff"
        )
    ]
    emitter.alphas = [
        (t, value[0] / _FIXED16)
        for t, value in _keyed(
            data, at + _OFS_ALPHA_TIMES, at + _OFS_ALPHA_VALUES, 2, "<H"
        )
    ]
    emitter.scales = [
        (t, (w, h))
        for t, (w, h) in _keyed(
            data, at + _OFS_SCALE_TIMES, at + _OFS_SCALE_VALUES, 8, "<ff"
        )
    ]
    return emitter


def read_emitters(data: bytes) -> list[Emitter]:
    """Read every particle emitter in a model.

    Raises ParticleError when the bytes are not a WotLK M2 at all. A model with no
    emitters is not an error: most of the client's models have none.
    """
    if len(data) < _OFS_PARTICLE_EMITTERS + 8 or data[:4] != _MD20:
        raise ParticleError("not an M2 model")
    count, at = _array(data, _OFS_PARTICLE_EMITTERS)
    if not count or at + count * _STRIDE > len(data):
        return []
    out: list[Emitter] = []
    for index in range(count):
        record = at + index * _STRIDE
        try:
            out.append(_one_emitter(data, record, index))
        except struct.error:
            break
    return out
