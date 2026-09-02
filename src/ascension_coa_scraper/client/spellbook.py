"""Resolve every spell in the client into a queryable book.

`client effects` answers for the spells one class's talents name -- a few hundred. This
answers for all of them: 239,062 rows in this client's Spell.dbc, of which 232,722 carry
a name and something to show.

That is too much to hand a browser as JSON and too much to re-derive per request, so it
is built once into SQLite. The point is the same as everywhere else in this project:
the viewer needs no game install and no StormLib at serve time, only the file this
produces.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from . import schema
from .effects import EffectResolver, SpellEffects
from .reader import Client

__all__ = ["SCHEMA_VERSION", "BuildStats", "build", "connect", "search", "fetch"]

SCHEMA_VERSION = 1

_DDL = """
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE spells (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    rank         TEXT,
    description  TEXT,
    icon         TEXT,
    visual_id    INTEGER NOT NULL DEFAULT 0,
    model_count  INTEGER NOT NULL DEFAULT 0,
    sound_count  INTEGER NOT NULL DEFAULT 0,
    -- Which class this spell belongs to, and as what. JSON list, null when the spell
    -- belongs to none -- most do not, being internal or creature spells.
    owners       TEXT,
    -- The resolved cast, as the viewer already renders it. Null when the spell has
    -- no visual at all, which is a little under half of them.
    effects      TEXT
);
"""

# Built after the insert, because filling a table with live indexes is far slower.
_INDEXES = """
CREATE INDEX spells_name ON spells (name COLLATE NOCASE);
CREATE INDEX spells_showy ON spells (model_count DESC, sound_count DESC);
CREATE INDEX spells_owned ON spells (owners) WHERE owners IS NOT NULL;
"""

#: Ascension ships its class catalogue as plain JSON beside the archives. It is what
#: says a spell is a class's own ability rather than only a talent's payload -- the
#: distinction the viewer would otherwise have no way to draw.
ADVANCEMENT = "CharacterAdvancementData.json"


@dataclass
class BuildStats:
    total: int = 0
    named: int = 0
    with_effects: int = 0
    with_owner: int = 0
    models: int = 0
    sounds: int = 0


def load_owners(content: Path) -> dict[int, list[dict]]:
    """Map spell id -> the class entries that grant it.

    A spell can be granted more than once: the same effect often appears as a class
    ability and again as a talent that upgrades it, and that is worth showing rather
    than collapsing.
    """
    path = content / ADVANCEMENT
    if not path.is_file():
        return {}
    owners: dict[int, list[dict]] = {}
    for entry in json.loads(path.read_text(encoding="utf-8")):
        record = {
            "name": entry.get("Name"),
            "class": entry.get("Class"),
            "tab": entry.get("Tab"),
            "type": entry.get("Type"),
            "level": entry.get("RequiredLevel") or None,
        }
        if not record["class"]:
            continue
        for spell_id in entry.get("Spells") or []:
            bucket = owners.setdefault(spell_id, [])
            if record not in bucket:
                bucket.append(record)
    return owners


def _payload(fx: SpellEffects) -> dict:
    """The same shape `client effects` writes, so the viewer renders one code path."""
    return {
        "spell_id": fx.spell_id,
        "name": fx.name,
        "rank": fx.rank or None,
        "icon": fx.icon,
        "visual_id": fx.visual_id,
        "models": fx.model_paths(),
        "sounds": fx.sound_paths(),
        "kits": [
            {
                "slot": kit.slot,
                "kit_id": kit.kit_id,
                "anim_id": kit.anim_id,
                "models": kit.models,
                "sound": (
                    {"id": kit.sound.id, "name": kit.sound.name,
                     "files": list(kit.sound.paths)}
                    if kit.sound else None
                ),
            }
            for kit in fx.kits
        ],
        "missile_model": fx.missile_model,
        "missile_sound": (
            {"id": fx.missile_sound.id, "name": fx.missile_sound.name,
             "files": list(fx.missile_sound.paths)}
            if fx.missile_sound else None
        ),
    }


def _rows(client: Client, stats: BuildStats,
          owners: dict[int, list[dict]]) -> Iterator[tuple]:
    resolver = EffectResolver(client)
    for row in client.dbc("Spell").rows(schema.SPELL):
        stats.total += 1
        name = (row.get("name") or "").strip()
        if not name:
            # Unnamed rows are internal placeholders; nothing to search for or show.
            continue
        stats.named += 1

        fx = resolver.resolve(row)
        payload = _payload(fx) if fx.kits or fx.missile_model else None
        models, sounds = len(fx.model_paths()), len(fx.sound_paths())
        if payload:
            stats.with_effects += 1
            stats.models += models
            stats.sounds += sounds

        owned = owners.get(row["id"])
        if owned:
            stats.with_owner += 1

        yield (
            row["id"], name, (row.get("rank") or "").strip() or None,
            (row.get("description") or "").strip() or None,
            fx.icon, fx.visual_id, models, sounds,
            json.dumps(owned, separators=(",", ":")) if owned else None,
            json.dumps(payload, separators=(",", ":")) if payload else None,
        )


def build(client: Client, path: Path, *, progress=None) -> BuildStats:
    """Resolve every named spell into ``path``, replacing anything already there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    stats = BuildStats()
    owners = load_owners(client.install.content)
    with sqlite3.connect(path) as db:
        db.executescript(_DDL)
        batch: list[tuple] = []
        for row in _rows(client, stats, owners):
            batch.append(row)
            if len(batch) >= 5000:
                db.executemany("INSERT INTO spells VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
                batch.clear()
                if progress:
                    progress(stats)
        if batch:
            db.executemany("INSERT INTO spells VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
        db.executescript(_INDEXES)
        db.executemany("INSERT INTO meta VALUES (?,?)", [
            ("schema_version", str(SCHEMA_VERSION)),
            ("spell_source", client.provider("DBFilesClient/Spell.dbc") or "?"),
            ("total", str(stats.total)),
            ("named", str(stats.named)),
            ("with_effects", str(stats.with_effects)),
            ("with_owner", str(stats.with_owner)),
        ])
    return stats


def connect(path: Path) -> sqlite3.Connection:
    """Open the book read-only, so serving it cannot alter it."""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def search(db: sqlite3.Connection, query: str, *, limit: int = 60) -> list[dict]:
    """Find spells by name, or by id when the query is a number.

    Names are ranked so that an exact match comes first, then a prefix, then anything
    containing it. Within each tier, a spell some class actually grants comes first,
    then whichever draws the most. Ties on name are the norm here -- 932 rows are
    called "Sample Persistent AoE" and dozens are called "Blizzard" -- and the one
    worth seeing is the one a class has, or failing that the one with a visual.
    """
    query = query.strip()
    if not query:
        return []

    if query.isdigit():
        rows = db.execute(
            "SELECT id, name, rank, icon, model_count, sound_count, owners "
            "FROM spells WHERE id = ? OR CAST(id AS TEXT) LIKE ? "
            "ORDER BY (id = ?) DESC, model_count DESC LIMIT ?",
            (int(query), query + "%", int(query), limit),
        ).fetchall()
        return [_row(r) for r in rows]

    like = _escape_like(query)
    rows = db.execute(
        "SELECT id, name, rank, icon, model_count, sound_count, owners FROM spells "
        "WHERE name LIKE ? ESCAPE '\\' "
        "ORDER BY CASE WHEN name = ? COLLATE NOCASE THEN 0 "
        "              WHEN name LIKE ? ESCAPE '\\' THEN 1 ELSE 2 END, "
        # A spell a class actually grants is nearly always the one being looked for.
        # Without this, "Blizzard" answers with unowned duplicates before the Mage's.
        "         (owners IS NULL), (model_count + sound_count) DESC, name, id "
        "LIMIT ?",
        (f"%{like}%", query, f"{like}%", limit),
    ).fetchall()
    return [_row(r) for r in rows]


def _row(record) -> dict:
    out = dict(record)
    if "owners" in out:
        out["owners"] = json.loads(out["owners"]) if out["owners"] else []
    return out


def _escape_like(query: str) -> str:
    """Make LIKE wildcards literal.

    Stripping them instead would turn a query of "%" into an empty pattern that
    matches every row, and would quietly fail anyone looking for a spell with a per
    cent sign in its name.
    """
    out = query.replace("\\", "\\\\")
    return out.replace("%", "\\%").replace("_", "\\_")


def fetch(db: sqlite3.Connection, spell_id: int) -> dict | None:
    """One spell, with its resolved cast if it has one."""
    row = db.execute(
        "SELECT id, name, rank, description, icon, visual_id, owners, effects "
        "FROM spells WHERE id = ?", (spell_id,),
    ).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["effects"] = json.loads(out["effects"]) if out["effects"] else None
    out["owners"] = json.loads(out["owners"]) if out["owners"] else []
    return out
