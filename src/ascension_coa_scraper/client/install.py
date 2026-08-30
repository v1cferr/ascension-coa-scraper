"""Locate an installed Ascension client and order its MPQ archives.

Load order matters because Ascension ships content as overlay patches: the same path
exists in several archives and the last one to load wins. Vanilla 3.3.5a only ever
loads ``patch-<X>.MPQ`` for a single character X, so its rule does not decide between
``patch-CA`` and ``patch-CHA``, which Ascension's own launcher adds. The order used
here is documented in `PATCH_ORDER_RULE` and is an assumption, not a fact read from
the client — so `Chain.conflicts` exists to make disagreement visible instead of
letting a wrong guess pass silently.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["InstallError", "Install", "Chain", "ArchiveRef", "find_install"]

_ENV_VAR = "ASCENSION_CLIENT"

# Relative to a Bottles/Wine prefix or a plain Windows install.
_KNOWN_SUFFIXES = (
    "drive_c/Program Files/Ascension Launcher/resources/ascension-live",
    "Ascension Launcher/resources/ascension-live",
    "resources/ascension-live",
    "ascension-live",
)

_BOTTLE_ROOTS = (
    Path.home() / ".local/share/bottles/bottles",
    Path.home() / ".var/app/com.usebottles.bottles/data/bottles/bottles",
)

# The seven archives a stock 3.3.5a client ships. Everything else under Data/ is
# either locale data or Ascension's own content.
BLIZZARD_BASE = (
    "common.MPQ", "common-2.MPQ", "expansion.MPQ", "lichking.MPQ",
    "patch.MPQ", "patch-2.MPQ", "patch-3.MPQ",
)

PATCH_ORDER_RULE = (
    "base archives in Blizzard's fixed order, then locale archives, then custom "
    "patch-<suffix> archives sorted by (length of suffix, suffix), so patch-A "
    "loads before patch-CA, which loads before patch-CHA. Later wins."
)

_PATCH_RE = re.compile(r"^patch-(?P<suffix>[0-9A-Za-z]+)\.mpq$", re.IGNORECASE)


class InstallError(RuntimeError):
    """No client directory could be identified."""


@dataclass(frozen=True)
class ArchiveRef:
    """One archive in the chain, with where it sits and why."""

    path: Path
    role: str          # "base" | "locale" | "custom" | "realm"
    order: int         # ascending; higher wins a path conflict
    size: int

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class Chain:
    """The archives of one install, in load order."""

    archives: list[ArchiveRef]
    #: path (lowercased) -> archive names that provide it, in load order
    providers: dict[str, list[str]] = field(default_factory=dict)

    def custom(self) -> list[ArchiveRef]:
        return [a for a in self.archives if a.role in {"custom", "realm"}]

    @property
    def conflicts(self) -> dict[str, list[str]]:
        """Paths provided by more than one archive, in load order."""
        return {p: names for p, names in self.providers.items() if len(names) > 1}

    def winner(self, path: str) -> str | None:
        """Which archive the client would actually read ``path`` from."""
        names = self.providers.get(path.replace("/", "\\").lower())
        return names[-1] if names else None


@dataclass
class Install:
    """A located client directory."""

    root: Path

    @property
    def data(self) -> Path:
        return self.root / "Data"

    @property
    def content(self) -> Path:
        """Ascension ships part of its own data as plain JSON, outside any archive."""
        return self.data / "Content"

    @property
    def wdb(self) -> Path:
        """Server-sent caches. Only ever populated by playing; not reproducible offline."""
        return self.root / "Cache" / "WDB"

    def locale_dirs(self) -> list[Path]:
        return sorted(
            p for p in self.data.iterdir()
            if p.is_dir() and re.fullmatch(r"[a-z]{2}[A-Z]{2}", p.name)
        )

    def realm_dirs(self) -> list[Path]:
        """Realm overlay folders, each declaring extra archives in ``listarchive``."""
        return sorted(p for p in self.data.iterdir() if p.is_dir() and (p / "listarchive").exists())

    def chain(self) -> Chain:
        """Every archive this install would load, in order."""
        archives: list[ArchiveRef] = []
        order = 0

        def add(path: Path, role: str) -> None:
            nonlocal order
            if path.exists():
                archives.append(ArchiveRef(path, role, order, path.stat().st_size))
                order += 1

        for name in BLIZZARD_BASE:
            add(self.data / name, "base")

        for locale in self.locale_dirs():
            for path in sorted(locale.glob("*.MPQ")) + sorted(locale.glob("*.mpq")):
                add(path, "locale")

        for path in _sorted_patches(self.data):
            if path.name in BLIZZARD_BASE:
                continue
            add(path, "custom")

        for realm in self.realm_dirs():
            declared = (realm / "listarchive").read_text(encoding="utf-8", errors="replace")
            for line in (ln.strip() for ln in declared.splitlines()):
                if line:
                    add(realm / line, "realm")

        return Chain(archives)


def _sorted_patches(data: Path) -> list[Path]:
    """Custom patch archives, ordered by `PATCH_ORDER_RULE`.

    Numeric suffixes sort before alphabetic ones, matching the vanilla client, which
    loads patch-4 through patch-9 ahead of patch-A through patch-Z.
    """
    patches: list[tuple[tuple[int, int, str], Path]] = []
    for path in data.iterdir():
        match = _PATCH_RE.match(path.name)
        if not match:
            continue
        suffix = match.group("suffix").upper()
        patches.append(((len(suffix), 0 if suffix.isdigit() else 1, suffix), path))
    return [path for _, path in sorted(patches)]


def _candidate_roots() -> Iterator[Path]:
    override = os.environ.get(_ENV_VAR)
    if override:
        yield Path(override)
    for bottles in _BOTTLE_ROOTS:
        if not bottles.is_dir():
            continue
        for bottle in sorted(bottles.iterdir()):
            for suffix in _KNOWN_SUFFIXES:
                yield bottle / suffix
    for base in (Path.home(), Path.home() / "Games", Path("/opt")):
        for suffix in _KNOWN_SUFFIXES:
            yield base / suffix


def find_install(path: str | os.PathLike[str] | None = None) -> Install:
    """Locate a client directory, or raise with what was tried."""
    if path is not None:
        root = Path(path)
        if not (root / "Data").is_dir():
            raise InstallError(f"{root} has no Data/ directory")
        return Install(root)

    tried: list[Path] = []
    for candidate in _candidate_roots():
        tried.append(candidate)
        if (candidate / "Data").is_dir():
            return Install(candidate)
    raise InstallError(
        "no Ascension client found; point " + _ENV_VAR + " at the directory that "
        "contains Data/, or pass --client. Tried:\n  "
        + "\n  ".join(str(p) for p in tried[:8])
    )
