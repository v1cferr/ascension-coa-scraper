import json

import pytest

from ascension_coa_scraper.flight import (
    FlightParseError,
    extract_payload,
    parse_html,
    parse_rows,
)


def _page(*fragments: str) -> str:
    """Wrap Flight fragments in a minimal HTML shell, the way Next.js emits them."""
    pushes = "".join(f"<script>self.__next_f.push([1,{json.dumps(f)}])</script>" for f in fragments)
    return f"<!DOCTYPE html><html><body>{pushes}</body></html>"


def test_extract_payload_joins_fragments_in_document_order():
    assert extract_payload(_page('1:"a"\n', '2:"b"\n')) == '1:"a"\n2:"b"\n'


def test_extract_payload_rejects_a_page_without_flight_data():
    with pytest.raises(FlightParseError):
        extract_payload("<html><body>nothing here</body></html>")


def test_extract_payload_tolerates_whitespace_after_the_comma():
    html = '<script>self.__next_f.push([1, "9:{\\"ok\\":true}\\n"])</script>'

    assert extract_payload(html) == '9:{"ok":true}\n'


def test_extract_payload_ignores_non_string_pushes():
    html = _page('1:"a"\n').replace("</body>", "<script>self.__next_f.push([1,0])</script></body>")
    assert extract_payload(html) == '1:"a"\n'


def test_parse_rows_reads_newline_delimited_json_rows():
    rows = parse_rows('0:{"a":1}\n1:["x","y"]\n')

    assert rows["0"].as_json() == {"a": 1}
    assert rows["1"].as_json() == ["x", "y"]


def test_parse_rows_consumes_text_chunks_by_length_including_newlines():
    # `T5,` declares 5 bytes: "a\nb\nc". The embedded newlines must not end the row.
    rows = parse_rows('4e:T5,a\nb\nc\n9:{"ok":true}\n')

    assert rows["4e"].text == "a\nb\nc"
    assert rows["9"].as_json() == {"ok": True}


def test_parse_rows_counts_bytes_not_characters():
    # "café" is 4 characters but 5 UTF-8 bytes.
    rows = parse_rows('7:T5,café\n8:"next"\n')

    assert rows["7"].text == "café"
    assert rows["8"].as_json() == "next"


def test_parse_rows_handles_o_chunks_without_swallowing_later_rows():
    # Observed in segment-prefetch streams: `o<len>,` bodies are length-prefixed too,
    # and are not newline-terminated before the next row id.
    rows = parse_rows('19:o1,~19:o3,abc1:"fragment"\n')

    assert rows["19"].text == "~abc"
    assert rows["1"].as_json() == "fragment"


def test_parse_rows_concatenates_repeated_row_ids_in_arrival_order():
    rows = parse_rows('9:{"part":\n9:1}\n')

    assert rows["9"].as_json() == {"part": 1}


def test_as_json_returns_none_for_non_json_rows():
    rows = parse_rows('2:I[339756,["/chunk.js"],"default"]\n')

    assert rows["2"].as_json() is None
    assert rows["2"].text.startswith("I[")


def test_parse_html_end_to_end():
    rows = parse_html(_page('9:{"talents":{"classes":[]}}\n'))

    assert rows["9"].as_json() == {"talents": {"classes": []}}
