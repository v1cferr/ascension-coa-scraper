"""Convert a raw realm payload into the normalized schema.

Every upstream quirk is absorbed here so :mod:`ascension_coa_scraper.models` can stay a
clean description of the data:

- ``entriesByTab`` is keyed ``"<classId>:<tabId>"``; we regroup it into trees.
- ``connectedNodeIds`` and ``requiredIds`` are fixed-width arrays padded with zeros.
- ``group`` uses ``0`` as "no group" rather than null.
- ``isStartingNode`` is an int that is not always 0 or 1.
- Descriptions arrive as pre-rendered tooltip HTML; we keep it and add a text rendering.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from html import unescape
from typing import Any

from . import SCHEMA_VERSION, __version__, classmeta
from .discovery import RawRealm
from .icons import SpriteSheet, class_icon_key, icon_key
from .models import (
    SHARED_CLASS_TAB_ID,
    ClassDataset,
    ClassInfo,
    Costs,
    EntryType,
    ExtractionMeta,
    Icon,
    NodeShape,
    Position,
    RealmRef,
    Requirements,
    SpriteRef,
    Talent,
    TalentRank,
    TalentTree,
)

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]*>")
_SPACE_RE = re.compile(r"[ \t]+")
_SLUG_QUOTE_RE = re.compile(r"['‘’]")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")

_ENTRY_TYPES = {"talent": EntryType.TALENT, "ability": EntryType.ABILITY}
_NODE_SHAPES = {
    "spendcircle": NodeShape.CIRCLE,
    "spendsquare": NodeShape.SQUARE,
    "spendhex": NodeShape.HEX,
}


class NormalizeError(RuntimeError):
    """Raised when the payload does not contain what was asked for."""


def strip_html(html: str) -> str:
    """Render tooltip HTML as plain text, turning ``<br>`` into line breaks."""
    if not html:
        return ""
    text = _BR_RE.sub("\n", html)
    text = _TAG_RE.sub("", text)
    text = unescape(text)
    text = _SPACE_RE.sub(" ", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def slugify(value: str) -> str:
    """Make a filesystem- and URL-safe slug, e.g. \"Vol'Jin Alpha\" -> 'voljin-alpha'.

    Apostrophes are dropped rather than turned into separators, which is what the site
    itself does for realm slugs.
    """
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    folded = _SLUG_QUOTE_RE.sub("", folded)
    return _SLUG_STRIP_RE.sub("-", folded.lower()).strip("-")


def _compact_ids(values: Any) -> list[int]:
    """Drop the zero padding upstream uses to keep these arrays fixed-width."""
    if not isinstance(values, list):
        return []
    return [int(v) for v in values if isinstance(v, int) and v != 0]


def _build_icon(source_path: str, key: str, sheet: SpriteSheet | None) -> Icon:
    sprite = None
    if sheet is not None:
        cell = sheet.locate(key)
        if cell is not None:
            sprite = SpriteRef(
                sheet_url=sheet.url,
                column=cell[0],
                row=cell[1],
                columns=sheet.columns,
                rows=sheet.rows,
            )
    return Icon(source_path=source_path, key=key, sprite=sprite)


def _normalize_rank(raw: Any, fallback_html: str) -> TalentRank | None:
    if not isinstance(raw, dict):
        return None
    html = raw.get("description") or fallback_html or ""
    spell_id = raw.get("spellId")
    return TalentRank(
        rank=int(raw.get("rank", 1)),
        spell_id=int(spell_id) if isinstance(spell_id, int) else None,
        description_html=html,
        description=strip_html(html),
    )


def normalize_talent(raw: dict[str, Any], sheet: SpriteSheet | None) -> Talent:
    """Convert one upstream entry into a :class:`~ascension_coa_scraper.models.Talent`."""
    name = str(raw.get("name", ""))
    description_html = str(raw.get("description", "") or "")
    icon_path = str(raw.get("iconPath", "") or "")
    spell_id = raw.get("spellId")

    ranks = [
        rank
        for rank in (
            _normalize_rank(entry, description_html) for entry in raw.get("rankDescriptions") or []
        )
        if rank is not None
    ]

    return Talent(
        id=int(raw.get("id", 0)),
        name=name,
        slug=slugify(name),
        entry_type=_ENTRY_TYPES.get(str(raw.get("entryType", "")).lower(), EntryType.TALENT),
        node_shape=_NODE_SHAPES.get(str(raw.get("nodeType", "")).lower(), NodeShape.UNKNOWN),
        is_passive=bool(raw.get("isPassive", 0)),
        is_starting_node=bool(raw.get("isStartingNode", 0)),
        max_ranks=int(raw.get("maxPoints", 1) or 1),
        class_id=int(raw.get("classId", 0)),
        tree_id=int(raw.get("tabId", 0)),
        position=Position(x=float(raw.get("x", 0)), y=float(raw.get("y", 0))),
        costs=Costs(
            talent_essence=int(raw.get("teCost", 0) or 0),
            ability_essence=int(raw.get("aeCost", 0) or 0),
        ),
        requirements=Requirements(
            tree_talent_essence=int(raw.get("reqTabTE", 0) or 0),
            tree_ability_essence=int(raw.get("reqTabAE", 0) or 0),
            level=int(raw.get("requiredLevel", 0) or 0),
            talent_ids=_compact_ids(raw.get("requiredIds")),
        ),
        spell_id=int(spell_id) if isinstance(spell_id, int) else None,
        spell_ids=_compact_ids(raw.get("spellIds")),
        description_html=description_html,
        description=strip_html(description_html),
        ranks=ranks,
        connections=_compact_ids(raw.get("connectedNodeIds")),
        choice_group=int(raw["group"]) if raw.get("group") else None,
        icon=_build_icon(icon_path, icon_key(icon_path), sheet),
        sort_order=int(raw.get("sortOrder", 0) or 0),
        flags=int(raw.get("flags", 0) or 0),
    )


def find_class(realm: RawRealm, wanted: str) -> dict[str, Any]:
    """Look up a class in a realm payload by name, slug, or numeric id.

    Raises:
        NormalizeError: if no class matches.
    """
    classes = realm.talents.get("classes") or []
    target = slugify(wanted)

    for entry in classes:
        name = str(entry.get("className", ""))
        if target in {slugify(name), str(entry.get("classId"))}:
            return entry

    available = ", ".join(sorted(slugify(str(c.get("className", ""))) for c in classes))
    raise NormalizeError(
        f"class {wanted!r} not found in realm {realm.slug!r} (available: {available})"
    )


def list_classes(realm: RawRealm) -> list[tuple[int, str, str]]:
    """Return ``(class_id, name, slug)`` for every class in a realm payload."""
    return [
        (
            int(c.get("classId", 0)),
            str(c.get("className", "")),
            slugify(str(c.get("className", ""))),
        )
        for c in realm.talents.get("classes") or []
    ]


def _content_hash(trees: list[TalentTree]) -> str:
    """Hash the talent data only, so re-running without upstream changes is stable."""
    payload = [tree.model_dump(mode="json") for tree in trees]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_class(
    realm: RawRealm,
    wanted_class: str,
    source_url: str,
    sheet: SpriteSheet | None = None,
    scraped_at: datetime | None = None,
) -> ClassDataset:
    """Build a complete :class:`ClassDataset` for one class of a realm payload."""
    raw_class = find_class(realm, wanted_class)
    class_id = int(raw_class.get("classId", 0))
    class_name = str(raw_class.get("className", ""))

    entries_by_tab = realm.talents.get("entriesByTab") or {}
    trees: list[TalentTree] = []

    for tab in sorted(raw_class.get("tabs") or [], key=lambda t: t.get("sortOrder", 0)):
        tab_id = int(tab.get("tabId", 0))
        tab_name = str(tab.get("tabName", ""))
        raw_entries = entries_by_tab.get(f"{class_id}:{tab_id}") or []

        talents = [normalize_talent(entry, sheet) for entry in raw_entries]
        talents.sort(key=lambda t: (t.position.y, t.position.x, t.sort_order, t.id))

        trees.append(
            TalentTree(
                id=tab_id,
                name=tab_name,
                slug=slugify(tab_name) or f"tab-{tab_id}",
                sort_order=int(tab.get("sortOrder", 0) or 0),
                class_id=class_id,
                is_shared=tab_id == SHARED_CLASS_TAB_ID,
                talents=talents,
            )
        )

    essence = (realm.talents.get("essenceByClass") or {}).get(str(class_id)) or {}
    meta = classmeta.get(class_id)

    class_info = ClassInfo(
        id=class_id,
        name=class_name,
        slug=slugify(class_name),
        class_file=meta.class_file if meta else None,
        color=meta.color if meta else None,
        max_talent_essence=essence.get("maxTalentEssence"),
        max_ability_essence=essence.get("maxAbilityEssence"),
        icon=(
            _build_icon(f"class:{meta.class_file}", class_icon_key(meta.class_file), sheet)
            if meta
            else None
        ),
    )

    upstream = realm.upstream_schema_version
    extraction = ExtractionMeta(
        source=source_url,
        builder="coa",
        realm=RealmRef(id=realm.realm_id, slug=realm.slug, name=realm.name),
        scraped_at=(scraped_at or datetime.now(UTC)).isoformat(timespec="seconds"),
        schema_version=SCHEMA_VERSION,
        scraper_version=__version__,
        upstream_schema_version=upstream if isinstance(upstream, dict) else None,
        content_hash=_content_hash(trees),
        talent_count=sum(len(tree.talents) for tree in trees),
        tree_count=len(trees),
    )

    return ClassDataset(meta=extraction, **{"class": class_info}, trees=trees)
