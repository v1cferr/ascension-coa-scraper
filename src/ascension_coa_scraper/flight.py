"""Parser for the React Server Components ("Flight") payload embedded in Next.js pages.

The Ascension builder is a Next.js App Router page. Its server-rendered HTML carries
the whole RSC payload inline, split across a handful of

    self.__next_f.push([1, "<fragment>"])

calls. Concatenating every fragment in document order reconstructs the Flight stream.

The stream is a sequence of rows, each introduced by a hexadecimal row id and a colon::

    9:["$","$L4d",null,{...}]
    4e:T5c1,<1473 bytes of raw text>

Most rows run to the next newline and hold JSON. Some carry a *length-prefixed* body
instead: a single-letter tag, a hex byte count, a comma, then exactly that many bytes of
UTF-8 — which may itself contain newlines. Those must be consumed by length, not by
newline, or the rows that follow get swallowed.

A single row id may appear several times; React streams large rows in pieces that are
concatenated in arrival order.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

_PUSH_PREFIX = "self.__next_f.push([1,"

# Tags whose body is `<tag><hex-byte-length>,<body>` rather than newline-delimited.
# `T` is React's text chunk; `o` shows up in Next.js segment-prefetch streams.
_LENGTH_PREFIXED_TAGS = frozenset("To")

_LENGTH_PREFIXED_RE = re.compile(rb"([A-Za-z])([0-9a-fA-F]+),")


class FlightParseError(RuntimeError):
    """Raised when the Flight payload cannot be recovered from a page."""


@dataclass
class FlightRow:
    """One logical row of the Flight stream, with its chunks joined in arrival order."""

    row_id: str
    chunks: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(self.chunks)

    def as_json(self) -> object | None:
        """Decode the row as JSON, or return ``None`` when it is not valid JSON.

        Many rows are module references (``I[...]``) or raw text rather than JSON, so a
        failure here is expected and not an error.
        """
        raw = self.text
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (ValueError, RecursionError):
            return None


def extract_payload(html: str) -> str:
    """Concatenate every ``self.__next_f.push`` fragment in an HTML document.

    Raises:
        FlightParseError: if the document contains no Flight fragments.
    """
    decoder = json.JSONDecoder()
    fragments: list[str] = []
    cursor = 0

    while True:
        start = html.find(_PUSH_PREFIX, cursor)
        if start < 0:
            break
        value_at = start + len(_PUSH_PREFIX)
        try:
            fragment, cursor = decoder.raw_decode(html, value_at)
        except ValueError:
            # Not a fragment we understand (e.g. `push([2, ...])` variants); skip past
            # the prefix so the scan keeps making progress.
            cursor = value_at
            continue
        if isinstance(fragment, str):
            fragments.append(fragment)

    if not fragments:
        raise FlightParseError(
            "no self.__next_f.push(...) fragments found; the page is not a "
            "server-rendered Next.js App Router document"
        )
    return "".join(fragments)


def parse_rows(payload: str) -> dict[str, FlightRow]:
    """Split a Flight payload into rows keyed by row id.

    Operates on UTF-8 bytes because length-prefixed chunks count bytes, not characters.
    """
    data = payload.encode("utf-8")
    rows: dict[str, FlightRow] = {}
    pos = 0
    end = len(data)

    while pos < end:
        colon = data.find(b":", pos)
        if colon < 0:
            break
        row_id = data[pos:colon].decode("utf-8", "replace")
        body_at = colon + 1

        match = _LENGTH_PREFIXED_RE.match(data, body_at)
        if match and match.group(1).decode() in _LENGTH_PREFIXED_TAGS:
            length = int(match.group(2), 16)
            body_start = match.end()
            body_end = min(body_start + length, end)
            chunk = data[body_start:body_end].decode("utf-8", "replace")
            pos = body_end
            if data[pos : pos + 1] == b"\n":
                pos += 1
        else:
            line_end = data.find(b"\n", body_at)
            if line_end < 0:
                line_end = end
            chunk = data[body_at:line_end].decode("utf-8", "replace")
            pos = line_end + 1

        rows.setdefault(row_id, FlightRow(row_id)).chunks.append(chunk)

    return rows


def parse_html(html: str) -> dict[str, FlightRow]:
    """Convenience wrapper: extract the payload from HTML and split it into rows."""
    return parse_rows(extract_payload(html))
