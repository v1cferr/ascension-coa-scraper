"""Locate the talent dataset inside a parsed Flight payload.

The builder embeds its data as a prop of a client component, so the exact row id and
prop path are build-specific and change whenever the site is redeployed. Rather than
hard-coding ``rows["9"][3]["value"]``, we search the decoded rows for objects that
*look* like a realm payload. That keeps the scraper working across rebuilds and makes
breakage loud and specific when the upstream shape genuinely changes.

A realm object is recognised by carrying a ``talents`` mapping that itself contains
``classes`` and ``entriesByTab``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .flight import FlightRow

# Keys that must be present under `talents` for an object to count as a realm payload.
_TALENTS_MARKERS = ("classes", "entriesByTab")


class DatasetNotFoundError(RuntimeError):
    """Raised when no realm payload can be located in a page."""


@dataclass(frozen=True)
class RawRealm:
    """A realm payload exactly as the site shipped it, plus where it was found."""

    row_id: str
    data: dict[str, Any]

    @property
    def slug(self) -> str:
        return str(self.data.get("slug", ""))

    @property
    def name(self) -> str:
        return str(self.data.get("name", self.slug))

    @property
    def realm_id(self) -> int | None:
        value = self.data.get("id")
        return value if isinstance(value, int) else None

    @property
    def talents(self) -> dict[str, Any]:
        return self.data.get("talents") or {}

    @property
    def upstream_schema_version(self) -> Any:
        return self.data.get("schema_version")


def _looks_like_realm(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    talents = value.get("talents")
    return isinstance(talents, dict) and all(key in talents for key in _TALENTS_MARKERS)


def find_realms(rows: dict[str, FlightRow]) -> list[RawRealm]:
    """Return every realm payload found across the decoded Flight rows.

    Results keep the order in which they appear in the page, which matches the order
    the builder shows in its realm switcher.
    """
    found: list[RawRealm] = []
    seen: set[int] = set()

    for row_id, row in rows.items():
        decoded = row.as_json()
        if decoded is None:
            continue

        stack: list[Any] = [decoded]
        while stack:
            node = stack.pop()

            if _looks_like_realm(node):
                # Don't descend into a realm: its subtree is megabytes of talent data
                # and cannot contain another realm.
                if id(node) not in seen:
                    seen.add(id(node))
                    found.append(RawRealm(row_id=row_id, data=node))
                continue

            if isinstance(node, dict):
                stack.extend(reversed(list(node.values())))
            elif isinstance(node, list):
                stack.extend(reversed(node))

    return found


def select_realm(realms: list[RawRealm], slug: str | None = None) -> RawRealm:
    """Pick a realm by slug, or the first one when no slug is given.

    Raises:
        DatasetNotFoundError: if nothing matches.
    """
    if not realms:
        raise DatasetNotFoundError(
            "no realm payload found in the page; the builder's data shape likely "
            "changed — re-run the discovery steps in docs/DATA_SOURCE.md"
        )

    if slug is None:
        return realms[0]

    for realm in realms:
        if realm.slug == slug:
            return realm

    available = ", ".join(r.slug for r in realms) or "none"
    raise DatasetNotFoundError(f"realm {slug!r} not found in page (available: {available})")
