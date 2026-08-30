"""WDBC decoding, built on synthetic tables so the suite needs no game client."""

from __future__ import annotations

import struct

import pytest

from ascension_coa_scraper.client.dbc import (
    FLOAT,
    INT,
    LOC,
    STR,
    UINT,
    Column,
    Dbc,
    DbcError,
    Table,
)


def build_dbc(rows: list[tuple[int, ...]], field_count: int, strings: bytes = b"\0") -> bytes:
    """Assemble a WDBC file: header, fixed-width records, string block."""
    body = b"".join(struct.pack(f"<{field_count}I", *row) for row in rows)
    header = struct.pack(
        "<4sIIII", b"WDBC", len(rows), field_count, field_count * 4, len(strings)
    )
    return header + body + strings


def offset_of(strings: bytes, text: bytes) -> int:
    return strings.index(text)


def test_parses_a_minimal_table():
    dbc = Dbc.parse(build_dbc([(1, 7), (2, 9)], field_count=2))
    assert (dbc.record_count, dbc.field_count, dbc.record_size) == (2, 2, 8)
    assert dbc.raw_row(1) == (2, 9)


def test_rejects_a_file_that_is_not_wdbc():
    with pytest.raises(DbcError, match="not a WDBC file"):
        Dbc.parse(b"WDB2" + bytes(16))


def test_rejects_a_truncated_file():
    data = build_dbc([(1, 2)], field_count=2)
    with pytest.raises(DbcError, match="truncated"):
        Dbc.parse(data[:-4])


def test_rejects_a_variable_width_table():
    # record_size that is not 4 x field_count means an extended format this reader
    # would misread field-by-field.
    header = struct.pack("<4sIIII", b"WDBC", 1, 2, 12, 1)
    with pytest.raises(DbcError, match="variable-width"):
        Dbc.parse(header + bytes(12) + b"\0")


def test_decodes_ints_floats_and_strings():
    strings = b"\0Fireball\0"
    raw_float = struct.unpack("<I", struct.pack("<f", 2.5))[0]
    dbc = Dbc.parse(
        build_dbc([(42, offset_of(strings, b"Fireball"), raw_float, 2**32 - 3)],
                  field_count=4, strings=strings)
    )
    table = Table("T", (
        Column("id", UINT), Column("name", STR), Column("scale", FLOAT), Column("delta", INT),
    ))
    row = next(iter(dbc.rows(table)))
    assert row == {"id": 42, "name": "Fireball", "scale": 2.5, "delta": -3}


def test_decodes_array_columns_into_lists():
    dbc = Dbc.parse(build_dbc([(1, 10, 20, 30)], field_count=4))
    table = Table("T", (Column("id", UINT), Column("effect", INT, 3)))
    assert next(iter(dbc.rows(table)))["effect"] == [10, 20, 30]


def test_localised_column_takes_the_populated_slot():
    # A WotLK localised string is 16 offsets plus a flags word; a single-locale client
    # populates exactly one of them.
    strings = b"\0Shadow Bolt\0"
    slots = [0] * 16
    slots[0] = offset_of(strings, b"Shadow Bolt")
    dbc = Dbc.parse(build_dbc([(686, *slots, 0)], field_count=18, strings=strings))
    table = Table("T", (Column("id", UINT), Column("name", LOC)))
    assert next(iter(dbc.rows(table)))["name"] == "Shadow Bolt"


def test_offset_zero_is_the_empty_string():
    dbc = Dbc.parse(build_dbc([(1, 0)], field_count=2, strings=b"\0x\0"))
    table = Table("T", (Column("id", UINT), Column("name", STR)))
    assert next(iter(dbc.rows(table)))["name"] == ""


def test_string_offset_past_the_block_is_reported():
    dbc = Dbc.parse(build_dbc([(1, 9999)], field_count=2, strings=b"\0short\0"))
    table = Table("T", (Column("id", UINT), Column("name", STR)))
    with pytest.raises(DbcError, match="outside the string block"):
        next(iter(dbc.rows(table)))


def test_schema_narrower_than_the_file_is_refused_without_trailing():
    dbc = Dbc.parse(build_dbc([(1, 2, 3)], field_count=3))
    table = Table("T", (Column("id", UINT),))
    with pytest.raises(DbcError, match="declares 1 fields but the file has 3"):
        next(iter(dbc.rows(table)))


def test_trailing_schema_ignores_columns_it_does_not_declare():
    dbc = Dbc.parse(build_dbc([(1, 2, 3)], field_count=3))
    table = Table("T", (Column("id", UINT), Column("kept", INT)), trailing=True)
    assert next(iter(dbc.rows(table))) == {"id": 1, "kept": 2}


def test_trailing_schema_still_needs_its_own_columns_present():
    dbc = Dbc.parse(build_dbc([(1,)], field_count=1))
    table = Table("T", (Column("id", UINT), Column("missing", INT)), trailing=True)
    with pytest.raises(DbcError, match="needs 2 fields but the file has only 1"):
        next(iter(dbc.rows(table)))


def test_known_widths_reject_a_different_generation_of_the_same_table():
    # The real case this guards: Spell.dbc ships with 222, 234 and 239 fields in one
    # install, and a trailing schema wide enough for one is wrong for the others.
    dbc = Dbc.parse(build_dbc([(1,) * 239], field_count=239))
    table = Table(
        "Spell", (Column("id", UINT), Column("category", INT)),
        trailing=True, known_widths=(234,),
    )
    with pytest.raises(DbcError, match="describes the 234-field layout"):
        next(iter(dbc.rows(table)))


def test_known_widths_accept_the_generation_they_name():
    dbc = Dbc.parse(build_dbc([(1, 5)], field_count=2))
    table = Table("T", (Column("id", UINT), Column("category", INT)), known_widths=(2,))
    assert next(iter(dbc.rows(table))) == {"id": 1, "category": 5}
