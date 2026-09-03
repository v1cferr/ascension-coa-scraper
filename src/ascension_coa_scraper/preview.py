"""Turn client assets into something a browser can show.

Two conversions stand between the extracted files and a page that shows what an effect
looks like. Textures are BLP, which no browser reads, and models are M2, which nothing
short of a renderer reads. Neither is converted ahead of time: they are derived on
request from files already on disk, so nothing new is stored and the answer never goes
stale against the extraction.
"""

from __future__ import annotations

import io
from dataclasses import asdict
from pathlib import Path

from .client.model import M2Error, describe
from .client.particles import ParticleError, read_emitters

__all__ = [
    "PreviewError", "UnsupportedAsset", "safe_asset", "texture_png", "model_summary",
]

#: Pillow reads BLP1 and BLP2, which covers everything this client ships. It is an
#: optional dependency, so its absence is reported rather than raised as ImportError.
try:  # pragma: no cover - exercised by whether the extra is installed
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


class PreviewError(RuntimeError):
    """The asset is missing or outside the tree."""


class UnsupportedAsset(PreviewError):
    """The file is there and readable, but this cannot convert it.

    Kept apart from a plain miss because they call for different answers: one means
    re-run the extraction, the other means the format is beyond the decoder. A handful
    of Shadowlands-era textures use BLP alpha encodings Pillow does not implement.
    """


def safe_asset(assets: Path, relative: str) -> Path:
    """Resolve ``relative`` inside ``assets``, refusing anything that escapes it.

    The path arrives from a URL, so ``..`` and absolute paths have to be rejected on
    the resolved result rather than by inspecting the string.

    A model named ``.mdx`` is looked up as ``.m2`` when the literal name misses, the
    swap the client itself makes. The tables name a tenth of their models with the
    Warcraft III extension for files stored as M2, and without this those are reported
    as un-extracted while sitting right there on disk.
    """
    root = assets.resolve()
    cleaned = relative.replace("\\", "/").lstrip("/")

    for candidate_name in _name_candidates(cleaned):
        candidate = (root / candidate_name).resolve()
        if not candidate.is_relative_to(root):
            raise PreviewError("path escapes the asset tree")
        if candidate.is_file():
            return candidate

    raise PreviewError(f"{relative} is not in the extracted assets")


def _name_candidates(name: str) -> list[str]:
    lowered = name.lower()
    if lowered.endswith(".mdx"):
        return [name, name[:-4] + ".m2"]
    if lowered.endswith(".m2"):
        return [name, name[:-3] + ".mdx"]
    return [name]


def texture_png(path: Path) -> bytes:
    """Decode a BLP to PNG.

    Effect textures are premultiplied sprites meant to be drawn on black; they are
    returned with their alpha intact so the page can composite them the way the game
    would rather than flattening them here.
    """
    if Image is None:
        raise PreviewError(
            "Pillow is not installed; run: uv sync --extra assets"
        )
    try:
        with Image.open(path) as image:
            image.load()
            out = io.BytesIO()
            image.convert("RGBA").save(out, format="PNG", optimize=False)
    except (OSError, ValueError, NotImplementedError) as exc:
        raise UnsupportedAsset(f"cannot decode {path.name}: {exc}") from exc
    return out.getvalue()


def model_summary(path: Path, *, assets: Path) -> dict:
    """Describe a model, and say which of its textures can actually be shown."""
    try:
        info = describe(path.read_bytes())
    except (M2Error, OSError) as exc:
        raise UnsupportedAsset(f"cannot read {path.name}: {exc}") from exc

    textures = []
    for reference in info.textures:
        try:
            found = safe_asset(assets, reference)
        except PreviewError:
            textures.append({"path": reference, "available": False})
            continue
        textures.append({
            "path": found.relative_to(assets.resolve()).as_posix(),
            "available": True,
        })

    payload = asdict(info)
    payload["textures"] = textures
    payload["is_particle_only"] = info.is_particle_only
    payload["glows"] = info.glows
    payload["particles"] = _particles(path, textures)
    return payload


def _particles(path: Path, textures: list[dict]) -> list[dict]:
    """Every emitter, with enough of its motion to be replayed.

    Each emitter names its texture by index into the model's own list, which is
    meaningless to anything outside this file, so it is swapped here for the path the
    viewer can actually fetch. An emitter whose index points nowhere keeps a null
    rather than borrowing a neighbour's texture.
    """
    try:
        emitters = read_emitters(path.read_bytes())
    except (ParticleError, OSError):
        # An effect that cannot be replayed is still worth describing, so this is a
        # missing section and not a failed request.
        return []

    out = []
    for emitter in emitters:
        texture = None
        if 0 <= emitter.texture < len(textures):
            entry = textures[emitter.texture]
            texture = entry["path"] if entry["available"] else None
        out.append({
            "index": emitter.index,
            "position": list(emitter.position),
            "bone": emitter.bone,
            "kind": emitter.kind,
            "blend": emitter.blend,
            "texture": texture,
            "rows": emitter.rows,
            "cols": emitter.cols,
            "tiles": emitter.tiles,
            "tile_rotation": emitter.tile_rotation,
            "speed": emitter.speed,
            "speed_variation": emitter.speed_variation,
            "vertical_range": emitter.vertical_range,
            "horizontal_range": emitter.horizontal_range,
            "gravity": emitter.gravity,
            "lifespan": emitter.lifespan,
            "lifespan_variation": emitter.lifespan_variation,
            "emission_rate": emitter.emission_rate,
            "emission_rate_variation": emitter.emission_rate_variation,
            "area_length": emitter.area_length,
            "area_width": emitter.area_width,
            "z_source": emitter.z_source,
            "drag": emitter.drag,
            "base_spin": emitter.base_spin,
            "base_spin_variation": emitter.base_spin_variation,
            "spin": emitter.spin,
            "spin_variation": emitter.spin_variation,
            "colors": [[t, list(c)] for t, c in emitter.colors],
            "alphas": [[t, a] for t, a in emitter.alphas],
            "scales": [[t, list(s)] for t, s in emitter.scales],
            "head_cells": [[t, c] for t, c in emitter.head_cells],
            "resolved": emitter.resolved,
        })
    return out
