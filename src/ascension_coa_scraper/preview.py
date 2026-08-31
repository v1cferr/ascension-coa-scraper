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

__all__ = ["PreviewError", "safe_asset", "texture_png", "model_summary"]

#: Pillow reads BLP1 and BLP2, which covers everything this client ships. It is an
#: optional dependency, so its absence is reported rather than raised as ImportError.
try:  # pragma: no cover - exercised by whether the extra is installed
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


class PreviewError(RuntimeError):
    """The asset is missing, outside the tree, or cannot be converted."""


def safe_asset(assets: Path, relative: str) -> Path:
    """Resolve ``relative`` inside ``assets``, refusing anything that escapes it.

    The path arrives from a URL, so ``..`` and absolute paths have to be rejected on
    the resolved result rather than by inspecting the string.
    """
    root = assets.resolve()
    candidate = (root / relative.replace("\\", "/").lstrip("/")).resolve()
    if not candidate.is_relative_to(root):
        raise PreviewError("path escapes the asset tree")
    if not candidate.is_file():
        raise PreviewError(f"{relative} is not in the extracted assets")
    return candidate


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
        raise PreviewError(f"cannot decode {path.name}: {exc}") from exc
    return out.getvalue()


def model_summary(path: Path, *, assets: Path) -> dict:
    """Describe a model, and say which of its textures can actually be shown."""
    try:
        info = describe(path.read_bytes())
    except (M2Error, OSError) as exc:
        raise PreviewError(f"cannot read {path.name}: {exc}") from exc

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
    return payload
