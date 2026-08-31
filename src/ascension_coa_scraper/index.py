"""Build the manifest the viewer reads.

A static page served over plain HTTP cannot list a directory, so it needs to be told
what exists. `build` walks the scraped datasets and the resolved effects and writes one
small JSON file naming every realm, class and tree, plus which spells have effect data.

Kept deliberately thin: it records what is on disk rather than deriving anything, so a
stale manifest is a missing entry, never a wrong one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

__all__ = ["IndexError_", "ViewerIndex", "build", "build_search", "write"]

SCHEMA_VERSION = 1


class IndexError_(RuntimeError):
    """Nothing indexable was found."""


@dataclass
class TreeEntry:
    id: int
    name: str
    slug: str
    file: str
    talent_count: int
    is_shared: bool
    sort_order: int


@dataclass
class ClassEntry:
    id: int
    name: str
    slug: str
    color: str
    class_file: str
    talent_count: int
    max_talent_essence: int
    max_ability_essence: int
    icon: dict | None
    dir: str
    trees: list[TreeEntry] = field(default_factory=list)
    effects_file: str | None = None
    effects_spell_count: int = 0


@dataclass
class RealmEntry:
    slug: str
    name: str
    id: int
    dir: str
    classes: list[ClassEntry] = field(default_factory=list)


@dataclass
class ViewerIndex:
    schema_version: int
    sprite_sheet: str | None
    asset_root: str
    #: When the underlying scrape ran, taken from the datasets rather than from file
    #: mtimes, which a clone or a copy would reset.
    captured: str | None = None
    realms: list[RealmEntry] = field(default_factory=list)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _class_from_dataset(directory: Path, root: Path) -> tuple[ClassEntry, dict]:
    """Read a scraped class directory into an entry, plus its realm block."""
    index_files = [
        p for p in directory.glob("*.json")
        if _read(p).get("trees") is not None
    ]
    if not index_files:
        raise IndexError_(f"{directory} has no class index file")
    payload = _read(index_files[0])
    info = payload["class"]
    entry = ClassEntry(
        id=info["id"],
        name=info["name"],
        slug=info["slug"],
        color=info.get("color") or "rgb(160, 160, 160)",
        class_file=info.get("class_file") or info["slug"],
        talent_count=payload["meta"]["talent_count"],
        max_talent_essence=info.get("max_talent_essence") or 0,
        max_ability_essence=info.get("max_ability_essence") or 0,
        icon=info.get("icon"),
        dir=directory.relative_to(root).as_posix(),
        trees=[
            TreeEntry(
                id=t["id"], name=t["name"], slug=t["slug"], file=t["file"],
                talent_count=t["talent_count"], is_shared=t["is_shared"],
                sort_order=t["sort_order"],
            )
            for t in sorted(payload["trees"], key=lambda t: t["sort_order"])
        ],
    )
    return entry, payload["meta"]["realm"]


def build(root: Path, *, effects_dir: Path | None = None,
          sprite_sheet: Path | None = None, asset_root: Path | None = None) -> ViewerIndex:
    """Index every ``<root>/<realm>/<class>/`` dataset directory."""
    realms: list[RealmEntry] = []
    captured: str | None = None

    for realm_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if realm_dir.name.startswith((".", "_")) or realm_dir.name == "client":
            continue
        classes: list[ClassEntry] = []
        realm_info: dict | None = None
        for class_dir in sorted(p for p in realm_dir.iterdir() if p.is_dir()):
            try:
                entry, realm_info = _class_from_dataset(class_dir, root)
            except (IndexError_, KeyError, json.JSONDecodeError):
                continue
            stamp = _read(class_dir / f"{entry.slug}.json").get("meta", {}).get("scraped_at")
            if stamp and (captured is None or stamp > captured):
                captured = stamp
            if effects_dir is not None:
                # Effects are resolved per realm, because the realms reference different
                # spells for the same class. A flat file is accepted as a fallback so an
                # older layout still indexes.
                for candidate in (effects_dir / realm_dir.name / f"{entry.slug}.json",
                                  effects_dir / f"{entry.slug}.json"):
                    if candidate.exists():
                        entry.effects_file = candidate.relative_to(root).as_posix()
                        entry.effects_spell_count = _read(candidate).get("spell_count", 0)
                        break
            classes.append(entry)
        if classes and realm_info:
            realms.append(RealmEntry(
                slug=realm_info["slug"], name=realm_info["name"], id=realm_info["id"],
                dir=realm_dir.name, classes=classes,
            ))

    if not realms:
        raise IndexError_(f"no scraped datasets found under {root}")

    return ViewerIndex(
        schema_version=SCHEMA_VERSION,
        sprite_sheet=(
            sprite_sheet.relative_to(root).as_posix()
            if sprite_sheet and sprite_sheet.exists() else None
        ),
        asset_root=(asset_root.relative_to(root).as_posix() if asset_root else "client/assets"),
        captured=captured,
        realms=realms,
    )


#: Field order of a search row. Rows are arrays rather than objects because there is
#: one per talent across every realm -- roughly 40,000 of them -- and the key names
#: would otherwise outweigh the data.
SEARCH_FIELDS = ("name", "talent_id", "spell_id", "realm", "class", "tree")


def build_search(index: ViewerIndex, root: Path) -> dict:
    """A flat, compact talent index for the viewer's search box.

    Loaded on first search rather than at startup: it is the largest thing the viewer
    reads, and most sessions never search.
    """
    rows: list[list] = []
    for realm in index.realms:
        for entry in realm.classes:
            for tree in entry.trees:
                payload = _read(root / entry.dir / tree.file)
                for talent in payload.get("tree", {}).get("talents", []):
                    rows.append([
                        talent["name"],
                        talent["id"],
                        talent.get("spell_id") or 0,
                        realm.slug,
                        entry.slug,
                        tree.slug,
                    ])
    return {"schema_version": SCHEMA_VERSION, "fields": list(SEARCH_FIELDS), "rows": rows}


def write(index: ViewerIndex, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(index), indent=2, ensure_ascii=False), encoding="utf-8")
    return path
