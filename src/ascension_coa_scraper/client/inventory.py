"""Index every path in an install's archives, and which archive wins it.

The index is what makes targeted extraction possible: 77 archives holding hundreds of
thousands of paths, where the same path appears in several and only the last one counts.
Building it reads each archive's ``(listfile)`` and hash table, not its file data, so it
is fast relative to the 26 GB it describes.
"""

from __future__ import annotations

import ctypes
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .install import Chain
from .mpq import Archive, MpqError

__all__ = ["ArchiveScan", "InventoryResult", "build_inventory"]


@dataclass
class ArchiveScan:
    """What one archive turned out to contain."""

    name: str
    role: str
    order: int
    size: int
    file_count: int
    listed: bool          # False when the archive ships no (listfile)
    error: str | None = None
    by_extension: Counter[str] | None = None


@dataclass
class InventoryResult:
    scans: list[ArchiveScan]
    #: normalised lowercase path -> archive names that provide it, in load order
    providers: dict[str, list[str]]

    @property
    def unlisted(self) -> list[ArchiveScan]:
        """Archives whose contents could not be enumerated.

        MPQ stores name hashes, not names. An archive without a ``(listfile)`` still
        holds files, but their paths cannot be recovered from the archive alone — they
        have to be guessed from an external listfile. Reporting these is the difference
        between "this archive is empty" and "this archive is opaque".
        """
        return [s for s in self.scans if not s.listed and s.error is None and s.file_count == 0]

    def paths_in(self, archive: str) -> list[str]:
        return sorted(p for p, names in self.providers.items() if archive in names)

    def save(self, path: Path) -> None:
        """Persist the index.

        Building it opens all 77 archives and takes the better part of a minute, which
        is long enough that every command would otherwise pay it. The index depends
        only on the archives, so it is safe to reuse until the launcher patches them.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "version": 1,
            "archives": [
                {
                    "name": s.name, "role": s.role, "order": s.order, "size": s.size,
                    "file_count": s.file_count, "listed": s.listed, "error": s.error,
                    "by_extension": dict(s.by_extension or {}),
                }
                for s in self.scans
            ],
            "providers": self.providers,
        }), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> InventoryResult:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("version") != 1:
            raise ValueError(f"{path} is an index of version {raw.get('version')}, not 1")
        scans = [
            ArchiveScan(
                a["name"], a["role"], a["order"], a["size"], a["file_count"],
                a["listed"], a["error"], Counter(a["by_extension"]),
            )
            for a in raw["archives"]
        ]
        return cls(scans, raw["providers"])

    def find(self, *fragments: str) -> dict[str, list[str]]:
        """Every indexed path containing all ``fragments`` (case-insensitive)."""
        needles = [f.lower().replace("/", "\\") for f in fragments]
        return {
            path: names
            for path, names in self.providers.items()
            if all(n in path for n in needles)
        }


def _normalise(path: str) -> str:
    return path.replace("/", "\\").lower()


def _extension(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).suffix.lower() or "(none)"


def build_inventory(
    chain: Chain, lib: ctypes.CDLL, *, roles: set[str] | None = None
) -> InventoryResult:
    """Scan the chain and record, for each path, every archive that provides it.

    ``roles`` restricts the scan (e.g. ``{"custom", "realm"}`` to skip the ~17 GB of
    stock Blizzard archives, which are obtainable from any 3.3.5a client).
    """
    scans: list[ArchiveScan] = []
    providers: dict[str, list[str]] = {}

    for ref in chain.archives:
        if roles is not None and ref.role not in roles:
            continue
        try:
            with Archive(ref.path, lib) as archive:
                names = archive.list_files()
        except MpqError as exc:
            scans.append(
                ArchiveScan(ref.name, ref.role, ref.order, ref.size, 0, False, str(exc))
            )
            continue

        extensions: Counter[str] = Counter()
        for name in names:
            if name.startswith("("):        # (listfile), (attributes), (signature)
                continue
            extensions[_extension(name)] += 1
            providers.setdefault(_normalise(name), []).append(ref.name)

        scans.append(
            ArchiveScan(
                ref.name, ref.role, ref.order, ref.size,
                file_count=sum(extensions.values()),
                listed=bool(names),
                by_extension=extensions,
            )
        )

    chain.providers = providers
    return InventoryResult(scans, providers)
