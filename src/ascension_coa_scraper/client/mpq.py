"""Read-only MPQ access through StormLib.

The scraper half of this project is pure HTTP; this half reads the installed game
client, whose archives are MPQ v2. Rather than reimplement the format — the sticking
point being PKWARE implode, which WoW still uses for some blocks — this binds StormLib
with ctypes. Nothing is compiled at install time; the caller supplies the shared object.

On NixOS::

    nix build --no-link --print-out-paths nixpkgs#stormlib
    export ASCENSION_STORMLIB=<that path>/lib/libstorm.so
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

__all__ = ["MpqError", "Archive", "load_stormlib"]

# SFileOpenArchive flags. Read-only is not merely an optimisation: the archives being
# read are the user's only copy of content that is about to stop being distributed,
# and StormLib will happily rewrite an archive it opened for writing.
_STREAM_FLAG_READ_ONLY = 0x00000100

_ENV_VAR = "ASCENSION_STORMLIB"
_SEARCH_NAMES = ("libstorm.so", "libstorm.so.9", "libStorm.so", "libstorm.dylib")


class MpqError(RuntimeError):
    """StormLib refused an operation, or the library itself could not be found."""


class _FindData(ctypes.Structure):
    """StormLib's SFILE_FIND_DATA."""

    _fields_ = [
        ("cFileName", ctypes.c_char * 1024),
        ("szPlainName", ctypes.c_char_p),
        ("dwHashIndex", ctypes.c_uint32),
        ("dwBlockIndex", ctypes.c_uint32),
        ("dwFileSize", ctypes.c_uint32),
        ("dwFileFlags", ctypes.c_uint32),
        ("dwCompSize", ctypes.c_uint32),
        ("dwFileTimeLo", ctypes.c_uint32),
        ("dwFileTimeHi", ctypes.c_uint32),
        ("lcLocale", ctypes.c_uint32),
    ]


def _candidate_paths() -> Iterator[str]:
    override = os.environ.get(_ENV_VAR)
    if override:
        yield override
    found = ctypes.util.find_library("storm")
    if found:
        yield found
    yield from _SEARCH_NAMES


def load_stormlib(path: str | os.PathLike[str] | None = None) -> ctypes.CDLL:
    """Load libstorm and declare the signatures this module uses.

    ``path`` wins over ``$ASCENSION_STORMLIB``, which wins over the system loader.
    """
    tried: list[str] = []
    for candidate in ([str(path)] if path else list(_candidate_paths())):
        tried.append(candidate)
        try:
            lib = ctypes.CDLL(candidate)
        except OSError:
            continue
        _declare(lib)
        return lib
    raise MpqError(
        "could not load StormLib; tried " + ", ".join(tried) + ". "
        f"Build it and point {_ENV_VAR} at the shared object:\n"
        "  nix build --no-link --print-out-paths nixpkgs#stormlib"
    )


def _declare(lib: ctypes.CDLL) -> None:
    """Set argtypes/restypes.

    ctypes defaults every argument to int, which truncates the 64-bit handles StormLib
    returns. Declaring the signatures is what makes this work on 64-bit at all.
    """
    handle = ctypes.c_void_p
    lib.SFileOpenArchive.argtypes = [
        ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(handle)
    ]
    lib.SFileOpenArchive.restype = ctypes.c_int
    lib.SFileCloseArchive.argtypes = [handle]
    lib.SFileCloseArchive.restype = ctypes.c_int

    lib.SFileHasFile.argtypes = [handle, ctypes.c_char_p]
    lib.SFileHasFile.restype = ctypes.c_int

    lib.SFileOpenFileEx.argtypes = [
        handle, ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(handle)
    ]
    lib.SFileOpenFileEx.restype = ctypes.c_int
    lib.SFileGetFileSize.argtypes = [handle, ctypes.POINTER(ctypes.c_uint32)]
    lib.SFileGetFileSize.restype = ctypes.c_uint32
    lib.SFileReadFile.argtypes = [
        handle, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
    ]
    lib.SFileReadFile.restype = ctypes.c_int
    lib.SFileCloseFile.argtypes = [handle]
    lib.SFileCloseFile.restype = ctypes.c_int

    lib.SFileFindFirstFile.argtypes = [
        handle, ctypes.c_char_p, ctypes.POINTER(_FindData), ctypes.c_char_p
    ]
    lib.SFileFindFirstFile.restype = handle
    lib.SFileFindNextFile.argtypes = [handle, ctypes.POINTER(_FindData)]
    lib.SFileFindNextFile.restype = ctypes.c_int
    lib.SFileFindClose.argtypes = [handle]
    lib.SFileFindClose.restype = ctypes.c_int


class Archive:
    """One opened MPQ archive.

    Paths inside an archive are Windows-style and case-insensitive. Callers may pass
    either separator; it is normalised to a backslash on the way in.
    """

    def __init__(self, path: Path, lib: ctypes.CDLL) -> None:
        self.path = Path(path)
        self._lib = lib
        self._handle = ctypes.c_void_p()
        ok = lib.SFileOpenArchive(
            str(self.path).encode("utf-8"), 0, _STREAM_FLAG_READ_ONLY,
            ctypes.byref(self._handle),
        )
        if not ok:
            raise MpqError(f"could not open {self.path} (StormLib error {ctypes.get_errno()})")

    def close(self) -> None:
        if self._handle:
            self._lib.SFileCloseArchive(self._handle)
            self._handle = ctypes.c_void_p()

    def __enter__(self) -> Archive:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @staticmethod
    def _encode(name: str) -> bytes:
        return name.replace("/", "\\").encode("utf-8")

    def __contains__(self, name: str) -> bool:
        return bool(self._lib.SFileHasFile(self._handle, self._encode(name)))

    def list_files(self, mask: str = "*") -> list[str]:
        """Every path the archive's internal listfile names.

        An archive with no ``(listfile)`` returns nothing even though it holds files —
        MPQ stores name hashes, not names, so unlisted entries are unrecoverable
        without an external listfile. `inventory` reports that case rather than
        silently under-reporting.
        """
        data = _FindData()
        find = self._lib.SFileFindFirstFile(
            self._handle, mask.encode("utf-8"), ctypes.byref(data), None
        )
        if not find:
            return []
        names: list[str] = []
        try:
            while True:
                names.append(data.cFileName.decode("latin-1"))
                if not self._lib.SFileFindNextFile(find, ctypes.byref(data)):
                    break
        finally:
            self._lib.SFileFindClose(ctypes.c_void_p(find))
        return names

    def read(self, name: str) -> bytes:
        """Whole contents of one file, decompressed."""
        encoded = self._encode(name)
        file_handle = ctypes.c_void_p()
        if not self._lib.SFileOpenFileEx(self._handle, encoded, 0, ctypes.byref(file_handle)):
            raise MpqError(f"{name!r} not found in {self.path.name}")
        try:
            high = ctypes.c_uint32(0)
            low = self._lib.SFileGetFileSize(file_handle, ctypes.byref(high))
            size = (high.value << 32) | low
            buffer = ctypes.create_string_buffer(size)
            read = ctypes.c_uint32(0)
            ok = self._lib.SFileReadFile(
                file_handle, buffer, size, ctypes.byref(read), None
            )
            # StormLib reports reaching the end of the file as failure, so the return
            # value alone does not distinguish success from a genuinely short read.
            if not ok and read.value != size:
                raise MpqError(
                    f"short read on {name!r} in {self.path.name}: "
                    f"{read.value} of {size} bytes"
                )
            return buffer.raw[: read.value]
        finally:
            self._lib.SFileCloseFile(file_handle)


@contextmanager
def open_archive(path: Path, lib: ctypes.CDLL | None = None) -> Iterator[Archive]:
    archive = Archive(path, lib or load_stormlib())
    try:
        yield archive
    finally:
        archive.close()
