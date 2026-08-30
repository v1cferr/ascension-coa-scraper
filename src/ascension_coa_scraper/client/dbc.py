"""Read WDBC client database tables.

The format is deliberately simple: a 20-byte header, a block of fixed-width records
where every field is exactly four bytes, and a string block that string fields index
into by byte offset. What the format does *not* carry is which of int/float/string
each field is — that is external knowledge, supplied here as a `Table` schema.

Because the schema is external, a table whose column count has drifted will decode
into plausible-looking nonsense rather than fail. `Table.bind` therefore checks the
declared width against the file's own ``field_count`` and refuses to decode a
mismatch. On a client with 192,000 custom spells that check is the difference between
a dataset and a fabrication.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

__all__ = ["DbcError", "Column", "Table", "Dbc", "INT", "UINT", "FLOAT", "STR", "LOC"]

_HEADER = struct.Struct("<4sIIII")
_MAGIC = b"WDBC"

INT = "int"
UINT = "uint"
FLOAT = "float"
STR = "str"
LOC = "loc"      # WotLK localised string: 16 string offsets followed by a flags word

_WIDTH = {INT: 1, UINT: 1, FLOAT: 1, STR: 1, LOC: 17}


class DbcError(RuntimeError):
    """The file is not a WDBC table, or does not match the schema it was read with."""


@dataclass(frozen=True)
class Column:
    """One logical column, which may span several physical fields."""

    name: str
    kind: str = INT
    count: int = 1        # >1 declares an array, decoded to a list

    @property
    def width(self) -> int:
        return _WIDTH[self.kind] * self.count


@dataclass(frozen=True)
class Table:
    """A named column layout for one DBC.

    ``trailing`` allows a schema to describe only the leading columns of a table and
    ignore the rest, which is how the same schema survives a server adding columns to
    the end -- common in private-server clients.

    ``known_widths`` pins the total ``field_count`` values this layout is known to
    describe. It exists because ``trailing`` alone is not a safety net: an install
    carries several generations of the same table -- Spell.dbc appears with 222, 234
    and 239 fields across four archives -- and a schema wide enough to fit the leading
    columns of one is not thereby correct for another. Without the pin, reading the
    wrong generation yields rows that decode without error and mean nothing.
    """

    name: str
    columns: tuple[Column, ...]
    trailing: bool = False
    known_widths: tuple[int, ...] = ()

    @property
    def width(self) -> int:
        return sum(c.width for c in self.columns)

    def bind(self, dbc: Dbc) -> None:
        """Check this schema can describe ``dbc``, or explain why it cannot."""
        if self.known_widths and dbc.field_count not in self.known_widths:
            raise DbcError(
                f"{self.name}: this schema describes the {'/'.join(map(str, self.known_widths))}"
                f"-field layout, but the file has {dbc.field_count} fields. It is a "
                f"different generation of the table, not a wider one -- read it from an "
                f"archive that ships the expected layout, or write a schema for this one."
            )
        if self.trailing:
            if dbc.field_count < self.width:
                raise DbcError(
                    f"{self.name}: schema needs {self.width} fields but the file has "
                    f"only {dbc.field_count}"
                )
            return
        if dbc.field_count != self.width:
            raise DbcError(
                f"{self.name}: schema declares {self.width} fields but the file has "
                f"{dbc.field_count}. The client's layout differs from the one this "
                f"schema was written for; decoding anyway would produce plausible "
                f"nonsense. Compare against a known row before changing the schema."
            )


@dataclass
class Dbc:
    """One parsed DBC file."""

    data: bytes
    record_count: int
    field_count: int
    record_size: int
    string_size: int
    _records_at: int = field(repr=False, default=0)
    _strings_at: int = field(repr=False, default=0)

    @classmethod
    def parse(cls, data: bytes) -> Dbc:
        if len(data) < _HEADER.size:
            raise DbcError(f"too short to be a DBC ({len(data)} bytes)")
        magic, records, fields_, record_size, string_size = _HEADER.unpack_from(data, 0)
        if magic != _MAGIC:
            raise DbcError(f"not a WDBC file (magic {magic!r})")
        if record_size != fields_ * 4:
            raise DbcError(
                f"record size {record_size} is not 4 x {fields_} fields; this is a "
                "variable-width or extended table, which this reader does not handle"
            )
        records_at = _HEADER.size
        strings_at = records_at + records * record_size
        if len(data) < strings_at + string_size:
            raise DbcError(
                f"truncated: header promises {strings_at + string_size} bytes, got {len(data)}"
            )
        return cls(data, records, fields_, record_size, string_size, records_at, strings_at)

    def raw_row(self, index: int) -> tuple[int, ...]:
        offset = self._records_at + index * self.record_size
        return struct.unpack_from(f"<{self.field_count}I", self.data, offset)

    def string(self, offset: int) -> str:
        """Decode one string-block entry.

        Offset 0 is the format's empty string. Out-of-range offsets happen in
        hand-edited private-server tables and are reported rather than crashing the
        whole extraction.
        """
        if offset == 0:
            return ""
        start = self._strings_at + offset
        if not (self._strings_at <= start < self._strings_at + self.string_size):
            raise DbcError(f"string offset {offset} falls outside the string block")
        end = self.data.find(b"\0", start)
        if end == -1:
            end = self._strings_at + self.string_size
        return self.data[start:end].decode("utf-8", errors="replace")

    def rows(self, table: Table) -> Iterator[dict[str, Any]]:
        """Decode every record according to ``table``."""
        table.bind(self)
        for index in range(self.record_count):
            yield self._decode(table, self.raw_row(index))

    def _decode(self, table: Table, raw: tuple[int, ...]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        pos = 0
        for column in table.columns:
            values = []
            for _ in range(column.count):
                if column.kind == LOC:
                    # 16 locale slots; only the populated one is of interest, and in a
                    # single-locale client that is the first non-empty.
                    slots = raw[pos : pos + 16]
                    pos += 17          # 16 offsets + the flags word
                    values.append(next(
                        (self.string(s) for s in slots if s), ""
                    ))
                    continue
                word = raw[pos]
                pos += 1
                if column.kind == STR:
                    values.append(self.string(word))
                elif column.kind == FLOAT:
                    values.append(struct.unpack("<f", struct.pack("<I", word))[0])
                elif column.kind == INT:
                    values.append(word - 2**32 if word >= 2**31 else word)
                else:
                    values.append(word)
            out[column.name] = values[0] if column.count == 1 else values
        return out
