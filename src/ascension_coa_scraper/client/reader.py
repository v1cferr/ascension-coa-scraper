"""Read a named client file from whichever archive actually wins it.

`Install` knows the load order and `inventory` knows who provides what; this joins the
two so callers ask for ``DBFilesClient\\Spell.dbc`` and get the bytes the game would
use, without naming an archive. Which archive that was stays available as
`Client.provider`, because for a table with several generations in one install the
answer is part of the result.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from pathlib import Path

from .dbc import Dbc, Table
from .install import Install
from .inventory import InventoryResult, build_inventory
from .mpq import Archive, MpqError, load_stormlib

__all__ = ["Client", "open_client"]


@dataclass
class Client:
    """An install with its archive index built, ready for path lookups."""

    install: Install
    inventory: InventoryResult
    lib: ctypes.CDLL
    _open: dict[str, Archive] = field(default_factory=dict, repr=False)

    def provider(self, path: str) -> str | None:
        """Name of the archive the game would read ``path`` from."""
        names = self.inventory.providers.get(path.replace("/", "\\").lower())
        return names[-1] if names else None

    def providers(self, path: str) -> list[str]:
        """Every archive offering ``path``, in load order."""
        return list(self.inventory.providers.get(path.replace("/", "\\").lower(), ()))

    def _archive(self, name: str) -> Archive:
        if name not in self._open:
            for ref in self.install.chain().archives:
                if ref.name == name:
                    self._open[name] = Archive(ref.path, self.lib)
                    break
            else:
                raise MpqError(f"archive {name} is not in this install's chain")
        return self._open[name]

    def read(self, path: str) -> bytes:
        """Contents of ``path`` from the winning archive."""
        name = self.provider(path)
        if name is None:
            raise MpqError(f"{path!r} is in no archive of this install")
        return self._archive(name).read(path)

    def dbc(self, name: str) -> Dbc:
        """Parse ``DBFilesClient\\<name>.dbc`` from the winning archive."""
        return Dbc.parse(self.read(f"DBFilesClient\\{name}.dbc"))

    def table(self, name: str, schema: Table) -> list[dict]:
        """Decode a whole table, raising if the winner is a layout the schema rejects."""
        return list(self.dbc(name).rows(schema))

    def close(self) -> None:
        for archive in self._open.values():
            archive.close()
        self._open.clear()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def open_client(install: Install, *, lib: ctypes.CDLL | None = None,
                roles: set[str] | None = None, index: Path | None = None,
                refresh: bool = False) -> Client:
    """Index ``install`` and return a `Client`.

    ``roles`` narrows which archives are indexed. The default covers all of them,
    which is what table lookups need: the stock Blizzard archives still win paths that
    Ascension never overrode.

    ``index`` caches the archive index, which otherwise costs about a minute per run.
    It is reused as-is unless ``refresh`` is set, so re-index after the launcher
    patches the archives.
    """
    lib = lib or load_stormlib()
    if index is not None and index.exists() and not refresh:
        inventory = InventoryResult.load(index)
    else:
        inventory = build_inventory(install.chain(), lib, roles=roles)
        if index is not None:
            inventory.save(index)
    return Client(install, inventory, lib)
