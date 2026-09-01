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
    -- The resolved cast, as the viewer already renders it. Null when the spell has
    -- no visual at all, which is a little under half of them.
    effects      TEXT
);
"""

# Built after the insert, because filling a table with live indexes is far slower.
_INDEXES = """
CREATE INDEX spells_name ON spells (name COLLATE NOCASE);
CREATE INDEX spells_showy ON spells (model_count DESC, sound_count DESC);
"""


@dataclass
class BuildStats:
    total: int = 0
    named: int = 0
    with_effects: int = 0
    models: int = 0
    sounds: int = 0


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


def _rows(client: Client, stats: BuildStats) -> Iterator[tuple]:
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

        yield (
            row["id"], name, (row.get("rank") or "").strip() or None,
            (row.get("description") or "").strip() or None,
            fx.icon, fx.visual_id, models, sounds,
            json.dumps(payload, separators=(",", ":")) if payload else None,
        )


def build(client: Client, path: Path, *, progress=None) -> BuildStats:
    """Resolve every named spell into ``path``, replacing anything already there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    stats = BuildStats()
    with sqlite3.connect(path) as db:
        db.executescript(_DDL)
        batch: list[tuple] = []
        for row in _rows(client, stats):
            batch.append(row)
            if len(batch) >= 5000:
                db.executemany("INSERT INTO spells VALUES (?,?,?,?,?,?,?,?,?)", batch)
                batch.clear()
                if progress:
                    progress(stats)
        if batch:
            db.executemany("INSERT INTO spells VALUES (?,?,?,?,?,?,?,?,?)", batch)
        db.executescript(_INDEXES)
        db.executemany("INSERT INTO meta VALUES (?,?)", [
            ("schema_version", str(SCHEMA_VERSION)),
            ("spell_source", client.provider("DBFilesClient/Spell.dbc") or "?"),
            ("total", str(stats.total)),
            ("named", str(stats.named)),
            ("with_effects", str(stats.with_effects)),
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
    containing it; within each, spells that actually draw something come first. Ties
    on name are the norm here -- 932 rows are called "Sample Persistent AoE" -- and
    the one worth seeing is the one with a visual.
    """
    query = query.strip()
    if not query:
        return []

    if query.isdigit():
        rows = db.execute(
            "SELECT id, name, rank, icon, model_count, sound_count "
            "FROM spells WHERE id = ? OR CAST(id AS TEXT) LIKE ? "
            "ORDER BY (id = ?) DESC, model_count DESC LIMIT ?",
            (int(query), query + "%", int(query), limit),
        ).fetchall()
        return [dict(r) for r in rows]

    like = _escape_like(query)
    rows = db.execute(
        "SELECT id, name, rank, icon, model_count, sound_count FROM spells "
        "WHERE name LIKE ? ESCAPE '\\' "
        "ORDER BY CASE WHEN name = ? COLLATE NOCASE THEN 0 "
        "              WHEN name LIKE ? ESCAPE '\\' THEN 1 ELSE 2 END, "
        "         (model_count + sound_count) DESC, name, id "
        "LIMIT ?",
        (f"%{like}%", query, f"{like}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


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
        "SELECT id, name, rank, description, icon, visual_id, effects "
        "FROM spells WHERE id = ?", (spell_id,),
    ).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["effects"] = json.loads(out["effects"]) if out["effects"] else None
    return out
