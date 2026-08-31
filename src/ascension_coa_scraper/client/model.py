"""Read what an M2 model is made of.

A spell effect's file name says nothing about what it does. The header says a great
deal: whether the effect is geometry or pure particles, how many emitters drive it,
which textures it draws with, and — the part that decides how it reads on screen —
whether those textures are blended additively, which is what makes an effect glow.

Only the counts and the small fixed-size blocks are parsed. Vertices, bones and
animation tracks are left alone: nothing here renders the model, it only describes it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

__all__ = ["M2Error", "ModelInfo", "BLEND_MODES", "parse_textures", "describe"]

_MD20 = b"MD20"

#: Offsets of the (count, offset) pairs in a WotLK (version 264) header. Verified
#: against the client's own files: every offset lands inside the file and every count
#: is plausible for all three thousand-odd models this project extracts.
_COUNTS = {
    "global_sequences": 0x14,
    "animations": 0x1C,
    "bones": 0x2C,
    "vertices": 0x3C,
    "colors": 0x48,
    "textures": 0x50,
    "transparency": 0x58,
    "uv_animations": 0x60,
    "render_flags": 0x70,
    "texture_units": 0x88,
    "attachments": 0xF0,
    "events": 0x100,
    "lights": 0x108,
    "cameras": 0x110,
    "ribbon_emitters": 0x120,
    "particle_emitters": 0x128,
}

_OFS_VIEWS = 0x44
_TEXTURE_RECORD = struct.Struct("<IIII")     # type, flags, lenFilename, ofsFilename
_RENDER_FLAG = struct.Struct("<HH")          # flags, blendingMode

#: Blending modes, in the order the format numbers them. The name is what an artist
#: would call it; the note is why it matters when reading an effect.
BLEND_MODES = {
    0: "opaque",
    1: "alpha key",
    2: "alpha",
    3: "additive (no alpha)",
    4: "additive",
    5: "modulate",
    6: "modulate 2x",
}

#: Texture type 0 carries a filename; every other type is supplied by the game at
#: runtime (character skin, hair, item) and names no file.
_HARDCODED = 0


class M2Error(RuntimeError):
    """The bytes are not a WotLK M2, or a block runs past the end of the file."""


@dataclass
class ModelInfo:
    """What one model is made of."""

    name: str = ""
    version: int = 0
    views: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    textures: list[str] = field(default_factory=list)
    blend_modes: list[str] = field(default_factory=list)

    @property
    def is_particle_only(self) -> bool:
        """No geometry, only emitters -- the shape of most spell effects."""
        return not self.counts.get("vertices") and bool(self.counts.get("particle_emitters"))

    @property
    def glows(self) -> bool | None:
        """Whether anything is drawn additively, which is what reads as light.

        ``None`` when the model declares no render flags at all. That is the normal
        shape of a pure particle effect: its blending lives inside each emitter, which
        this does not parse, so the honest answer is "not known from here" rather
        than "no".
        """
        if not self.blend_modes:
            return None
        return any("additive" in mode for mode in self.blend_modes)


#: The header field each entry point reads furthest into, plus its own width.
_NEEDS_TEXTURES = 0x58
_NEEDS_FULL = 0x130


def _check(data: bytes, need: int = _NEEDS_TEXTURES) -> None:
    if data[:4] != _MD20:
        raise M2Error(f"not a WotLK M2 (magic {data[:4]!r})")
    if len(data) < need:
        raise M2Error(
            f"header stops at {len(data)} bytes; this read needs {need}"
        )


def _pair(data: bytes, offset: int) -> tuple[int, int]:
    count, at = struct.unpack_from("<II", data, offset)
    if count and not (0 < at <= len(data)):
        raise M2Error(f"a block at header offset {offset:#x} points outside the file")
    return count, at


def parse_textures(data: bytes) -> tuple[int, list[str]]:
    """``(view count, texture paths)``.

    View count is how many ``.skin`` files sit beside the model; texture paths are the
    ones the model names itself.
    """
    _check(data, _NEEDS_TEXTURES)
    (views,) = struct.unpack_from("<I", data, _OFS_VIEWS)
    count, at = _pair(data, _COUNTS["textures"])

    textures: list[str] = []
    for index in range(count):
        record = at + index * _TEXTURE_RECORD.size
        if record + _TEXTURE_RECORD.size > len(data):
            raise M2Error(f"texture record {index} runs past the end of the file")
        kind, _flags, length, name_at = _TEXTURE_RECORD.unpack_from(data, record)
        if kind != _HARDCODED or not length:
            continue
        if name_at + length > len(data):
            raise M2Error(f"texture name {index} runs past the end of the file")
        name = data[name_at : name_at + length].split(b"\0")[0]
        if name:
            textures.append(name.decode("latin-1").replace("/", "\\"))
    return views, textures


def _blend_modes(data: bytes) -> list[str]:
    count, at = _pair(data, _COUNTS["render_flags"])
    modes: list[str] = []
    for index in range(count):
        record = at + index * _RENDER_FLAG.size
        if record + _RENDER_FLAG.size > len(data):
            break
        _flags, mode = _RENDER_FLAG.unpack_from(data, record)
        modes.append(BLEND_MODES.get(mode, f"mode {mode}"))
    return modes


def describe(data: bytes) -> ModelInfo:
    """Summarise a model without rendering it."""
    _check(data, _NEEDS_FULL)
    (version,) = struct.unpack_from("<I", data, 0x04)
    length, at = struct.unpack_from("<II", data, 0x08)
    name = ""
    if length and at + length <= len(data):
        name = data[at : at + length].split(b"\0")[0].decode("latin-1", "replace")

    views, textures = parse_textures(data)
    counts = {}
    for label, offset in _COUNTS.items():
        try:
            counts[label] = _pair(data, offset)[0]
        except M2Error:
            counts[label] = 0

    return ModelInfo(
        name=name,
        version=version,
        views=views,
        counts=counts,
        textures=textures,
        blend_modes=_blend_modes(data),
    )
