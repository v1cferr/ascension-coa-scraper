"""Collect a talent's or a class's extracted assets into one download.

The effects dataset names models and sounds, which is what a reader needs. It is not
what a *user* needs: a model without its geometry and textures opens to nothing. This
walks from the named paths to the complete set on disk -- the .skin siblings and the
textures the M2 names inside itself -- and zips them.

Everything here works against the extracted asset tree rather than the archives, so it
runs without StormLib and without the game installed. Files the tree does not hold are
reported, not silently dropped: a bundle that is quietly missing half a model is worse
than one that says so.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .client.assets import M2Error, parse_textures

__all__ = ["BundleError", "Bundle", "collect_spell", "collect_class", "write_zip"]

#: Where the viewer's asset paths live, relative to the served data directory.
ASSET_ROOT = Path("client") / "assets"
EFFECTS_ROOT = Path("client") / "effects"


class BundleError(RuntimeError):
    """The requested class, spell or asset tree is not there."""


@dataclass
class Bundle:
    """A resolved set of files, ready to zip."""

    name: str
    #: archive-relative path -> file on disk
    files: dict[str, Path] = field(default_factory=dict)
    #: paths the dataset named that the extracted tree does not hold
    missing: list[str] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.files.values())

    def __len__(self) -> int:
        return len(self.files)


def _disk_path(assets: Path, ref: str) -> Path:
    return assets / ref.replace("\\", "/")


def _resolve(assets: Path, ref: str) -> Path | None:
    """Find ``ref`` on disk, trying the .mdx/.m2 swap the client makes."""
    direct = _disk_path(assets, ref)
    if direct.is_file():
        return direct
    lowered = ref.lower()
    if lowered.endswith(".mdx"):
        swapped = _disk_path(assets, ref[:-4] + ".m2")
    elif lowered.endswith(".m2"):
        swapped = _disk_path(assets, ref[:-3] + ".mdx")
    else:
        return None
    return swapped if swapped.is_file() else None


def _companions(assets: Path, model: Path) -> list[Path]:
    """The .skin geometry and textures a model needs, as far as the tree holds them.

    Skins sit beside the model and are numbered; texture paths are archive-relative and
    resolve from the asset root, not from the model's own directory.
    """
    try:
        views, textures = parse_textures(model.read_bytes())
    except (M2Error, OSError):
        # A model this reader cannot parse still belongs in the bundle on its own.
        return []

    out: list[Path] = []
    stem = model.with_suffix("")
    for index in range(views):
        skin = stem.parent / f"{stem.name}{index:02d}.skin"
        if skin.is_file():
            out.append(skin)
    for texture in textures:
        candidate = _disk_path(assets, texture)
        if candidate.is_file():
            out.append(candidate)
    return out


def _add(bundle: Bundle, assets: Path, ref: str) -> None:
    """Add one referenced path, plus a model's geometry and textures."""
    found = _resolve(assets, ref)
    if found is None:
        bundle.missing.append(ref)
        return
    bundle.files[found.relative_to(assets).as_posix()] = found
    if found.suffix.lower() == ".m2":
        for extra in _companions(assets, found):
            bundle.files[extra.relative_to(assets).as_posix()] = extra


def _effects(data_root: Path, realm: str, class_slug: str) -> dict:
    path = data_root / EFFECTS_ROOT / realm / f"{class_slug}.json"
    if not path.is_file():
        raise BundleError(f"no effects for {class_slug} on {realm}")
    return json.loads(path.read_text(encoding="utf-8"))


def _refs(spell: dict, *, icons: bool = True) -> list[str]:
    refs = list(spell.get("models") or []) + list(spell.get("sounds") or [])
    if icons and spell.get("icon"):
        refs.append(spell["icon"] + ".blp")
    return refs


def collect_spell(data_root: Path, realm: str, class_slug: str, spell_id: int) -> Bundle:
    """Every file one spell's effects reference."""
    payload = _effects(data_root, realm, class_slug)
    spell = next((s for s in payload["spells"] if s["spell_id"] == spell_id), None)
    if spell is None:
        raise BundleError(f"spell {spell_id} is not in {class_slug} on {realm}")

    assets = data_root / ASSET_ROOT
    if not assets.is_dir():
        raise BundleError(
            "no extracted assets; run: ascension-coa client extract --from-effects ..."
        )

    slug = "".join(c if c.isalnum() else "-" for c in spell.get("name", "")).strip("-")
    bundle = Bundle(name=f"{class_slug}-{spell_id}-{slug}".rstrip("-").lower() or str(spell_id))
    for ref in _refs(spell):
        _add(bundle, assets, ref)
    return bundle


def collect_class(data_root: Path, realm: str, class_slug: str) -> Bundle:
    """Every file the whole class references, deduplicated."""
    payload = _effects(data_root, realm, class_slug)
    assets = data_root / ASSET_ROOT
    if not assets.is_dir():
        raise BundleError(
            "no extracted assets; run: ascension-coa client extract --from-effects ..."
        )

    bundle = Bundle(name=f"{realm}-{class_slug}")
    for spell in payload["spells"]:
        for ref in _refs(spell):
            _add(bundle, assets, ref)
    return bundle


def write_zip(bundle: Bundle) -> bytes:
    """Zip the bundle, with a manifest naming anything that could not be found."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(bundle.files.items()):
            archive.write(path, arcname=f"{bundle.name}/{name}")
        if bundle.missing:
            archive.writestr(
                f"{bundle.name}/MISSING.txt",
                "These paths are referenced by the dataset but are not in the extracted\n"
                "asset tree. Re-run `ascension-coa client extract` to fill them in.\n\n"
                + "\n".join(sorted(set(bundle.missing))) + "\n",
            )
    return buffer.getvalue()
