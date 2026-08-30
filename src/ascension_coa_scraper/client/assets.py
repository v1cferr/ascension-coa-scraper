"""Turn a referenced model path into the full set of files needed to open it.

A model path taken from SpellVisualEffectName is not enough on its own. Three things
stand between it and a file a viewer can load:

* The table names some models ``.mdx``, the Warcraft III extension. The client swaps
  the suffix for ``.m2`` at load time and so must anything reading the archives --
  7 of Stormbringer's 94 model references are ``.mdx`` and none of them exist under
  that name.
* Geometry lives in sibling ``.skin`` files, one per view, named ``<model>00.skin``
  upward. The M2 header says how many.
* Textures are named inside the M2, not in any table.

`expand` resolves all three, so extraction writes models that actually open.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

__all__ = ["M2Error", "ModelFiles", "resolve_path", "parse_textures", "expand"]

_MD20 = b"MD20"
# Offsets into the WotLK (version 264) M2 header.
_OFS_N_VIEWS = 0x44
_OFS_N_TEXTURES = 0x50
_TEXTURE_RECORD = struct.Struct("<IIII")   # type, flags, lenFilename, ofsFilename

#: Texture type 0 means the filename is baked into the model. Every other type is
#: supplied by the game at runtime (character skin, hair, item texture) and carries
#: no filename to extract.
_HARDCODED = 0


class M2Error(RuntimeError):
    """The bytes are not a WotLK M2, or its texture block is inconsistent."""


@dataclass
class ModelFiles:
    """One model and everything it needs."""

    requested: str            # the path as the DBC named it
    model: str | None         # the path that actually exists, if any
    skins: list[str] = field(default_factory=list)
    textures: list[str] = field(default_factory=list)

    @property
    def all_paths(self) -> list[str]:
        return ([self.model] if self.model else []) + self.skins + self.textures


def resolve_path(path: str, exists) -> str | None:
    """The archive path for ``path``, trying the .mdx -> .m2 swap the client makes.

    ``exists`` is a predicate taking one path.
    """
    candidate = path.replace("/", "\\")
    if exists(candidate):
        return candidate
    lowered = candidate.lower()
    if lowered.endswith(".mdx"):
        swapped = candidate[:-4] + ".m2"
        if exists(swapped):
            return swapped
    elif lowered.endswith(".m2"):
        swapped = candidate[:-3] + ".mdx"
        if exists(swapped):
            return swapped
    return None


def parse_textures(data: bytes) -> tuple[int, list[str]]:
    """Return ``(view_count, texture_paths)`` from an M2 header.

    Only textures the model names itself are returned; the rest are supplied by the
    game at runtime and have no file to extract.
    """
    if len(data) < 0x58 or data[:4] != _MD20:
        raise M2Error(f"not a WotLK M2 (magic {data[:4]!r})")
    (views,) = struct.unpack_from("<I", data, _OFS_N_VIEWS)
    count, offset = struct.unpack_from("<II", data, _OFS_N_TEXTURES)

    textures: list[str] = []
    for index in range(count):
        record = offset + index * _TEXTURE_RECORD.size
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


def expand(path: str, exists, read) -> ModelFiles:
    """Resolve ``path`` and collect its skins and textures.

    A model whose header cannot be parsed still yields the model itself: half an asset
    is more useful than none, and the caller sees the empty companion lists.
    """
    resolved = resolve_path(path, exists)
    out = ModelFiles(requested=path, model=resolved)
    if resolved is None or not resolved.lower().endswith(".m2"):
        return out

    try:
        views, textures = parse_textures(read(resolved))
    except (M2Error, OSError):
        return out

    base = resolved[: -len(".m2")]
    out.skins = [p for i in range(views) if exists(p := f"{base}{i:02d}.skin")]
    out.textures = [t for t in textures if exists(t)]
    return out
