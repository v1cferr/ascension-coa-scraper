"""`ascension-coa client ...` subcommands.

Four verbs, in the order a run uses them: `inventory` builds the archive index,
`dump-dbc` writes decoded tables, `effects` joins spells to their models and sounds,
and `extract` pulls the referenced asset files out of the archives.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from . import schema
from .dbc import DbcError
from .effects import EffectResolver, SpellEffects
from .install import PATCH_ORDER_RULE, Install, InstallError, find_install
from .mpq import MpqError
from .reader import Client, open_client

CLIENT_ERRORS = (InstallError, MpqError, DbcError)

DEFAULT_INDEX = Path(".cache") / "client-index.json"


def _open(args: argparse.Namespace) -> tuple[Install, Client]:
    install = find_install(args.client)
    client = open_client(install, index=args.index, refresh=args.reindex)
    return install, client


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# --- inventory --------------------------------------------------------------------


def run_inventory(args: argparse.Namespace) -> int:
    install, client = _open(args)
    inventory = client.inventory

    print(f"client   {install.root}")
    print(f"archives {len(inventory.scans)}")
    print(f"paths    {len(inventory.providers):,} distinct")
    print(f"order    {PATCH_ORDER_RULE}\n")

    for scan in sorted(inventory.scans, key=lambda s: s.order):
        note = f"  ERROR: {scan.error}" if scan.error else ""
        if not scan.listed and not scan.error:
            note = "  no (listfile): contents not enumerable"
        print(f"  {scan.order:>3} {scan.role:<7} {scan.name:<22} "
              f"{scan.size / 2**20:>9.1f} MB {scan.file_count:>8,} files{note}")

    conflicts = {p: n for p, n in inventory.providers.items() if len(n) > 1}
    print(f"\n{len(conflicts):,} paths are provided by more than one archive")
    if args.out:
        payload = {
            "client": str(install.root),
            "patch_order_rule": PATCH_ORDER_RULE,
            "archives": [asdict(s) | {"by_extension": dict(s.by_extension or {})}
                         for s in inventory.scans],
            "conflicts": conflicts,
        }
        print("wrote", _write(args.out, payload))
    client.close()
    return 0


# --- dump-dbc ---------------------------------------------------------------------


def run_dump_dbc(args: argparse.Namespace) -> int:
    _, client = _open(args)
    names = args.tables or sorted(schema.TABLES)
    failures = 0
    for name in names:
        table = schema.TABLES.get(name)
        if table is None:
            print(f"error: no schema for {name}; known: {', '.join(sorted(schema.TABLES))}",
                  file=sys.stderr)
            failures += 1
            continue
        provider = client.provider(f"DBFilesClient/{name}.dbc")
        try:
            rows = client.table(name, table)
        except CLIENT_ERRORS as exc:
            print(f"error: {name}: {exc}", file=sys.stderr)
            failures += 1
            continue
        path = _write(args.out / f"{name}.json", {
            "table": name,
            "source_archive": provider,
            "providers": client.providers(f"DBFilesClient/{name}.dbc"),
            "record_count": len(rows),
            "rows": rows,
        })
        print(f"  {name:<24} {len(rows):>8,} rows  <- {provider}  -> {path}")
    client.close()
    return 1 if failures else 0


# --- effects ----------------------------------------------------------------------


def _spell_ids_from_dataset(directory: Path) -> dict[int, list[str]]:
    """Spell ids referenced by a scraped talent dataset, with the talents naming them."""
    used: dict[int, list[str]] = {}
    for path in sorted(directory.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        tree = payload.get("tree")
        if not tree:
            continue
        for talent in tree.get("talents", []):
            for spell_id in talent.get("spell_ids") or []:
                used.setdefault(spell_id, []).append(talent.get("name", "?"))
    return used


def _effects_payload(fx: SpellEffects, talents: list[str]) -> dict:
    return {
        "spell_id": fx.spell_id,
        "name": fx.name,
        "rank": fx.rank or None,
        "talents": sorted(set(talents)) or None,
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
                    {"id": kit.sound.id, "name": kit.sound.name, "files": list(kit.sound.paths)}
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


def run_effects(args: argparse.Namespace) -> int:
    _, client = _open(args)

    wanted: dict[int, list[str]] = {}
    if args.dataset:
        wanted = _spell_ids_from_dataset(args.dataset)
        if not wanted:
            print(f"error: no spell ids found under {args.dataset}", file=sys.stderr)
            return 1
    for spell_id in args.spell or []:
        wanted.setdefault(spell_id, [])

    resolver = EffectResolver(client)
    spell_rows = client.dbc("Spell").rows(schema.SPELL)
    selected = (
        [r for r in spell_rows if r["id"] in wanted] if wanted else list(spell_rows)
    )

    resolved = [(_effects_payload(resolver.resolve(r), wanted.get(r["id"], [])))
                for r in selected]
    missing = sorted(set(wanted) - {r["spell_id"] for r in resolved}) if wanted else []

    models = Counter(m for r in resolved for m in r["models"])
    sounds = Counter(s for r in resolved for s in r["sounds"])
    path = _write(args.out, {
        "source_archives": {
            name: client.provider(f"DBFilesClient/{name}.dbc")
            for name in ("Spell", "SpellVisual", "SpellVisualKit",
                         "SpellVisualEffectName", "SpellIcon", "SoundEntries")
        },
        "spell_count": len(resolved),
        "missing_spell_ids": missing,
        "distinct_models": len(models),
        "distinct_sounds": len(sounds),
        "spells": resolved,
    })
    print(f"  {len(resolved):,} spells resolved -> {path}")
    print(f"  {len(models):,} distinct models, {len(sounds):,} distinct sounds")
    if missing:
        print(f"  {len(missing)} requested spell ids are absent from Spell.dbc: "
              f"{missing[:8]}{' ...' if len(missing) > 8 else ''}", file=sys.stderr)
    client.close()
    return 0


# --- extract ----------------------------------------------------------------------


def run_extract(args: argparse.Namespace) -> int:
    _, client = _open(args)

    paths: list[str] = list(args.path or [])
    if args.from_effects:
        payload = json.loads(args.from_effects.read_text(encoding="utf-8"))
        for spell in payload.get("spells", []):
            paths.extend(spell.get("models") or [])
            paths.extend(spell.get("sounds") or [])
            if args.icons and spell.get("icon"):
                paths.append(spell["icon"] + ".blp")

    # Order-preserving dedup: the same model is referenced by many spells.
    seen: dict[str, None] = {}
    for path in paths:
        seen.setdefault(path.replace("/", "\\"), None)

    written = failed = absent = 0
    for path in seen:
        provider = client.provider(path)
        if provider is None:
            absent += 1
            if args.verbose:
                print(f"  absent  {path}", file=sys.stderr)
            continue
        target = args.out / path.replace("\\", "/")
        if target.exists() and not args.overwrite:
            continue
        try:
            data = client.read(path)
        except CLIENT_ERRORS as exc:
            failed += 1
            print(f"  failed  {path}: {exc}", file=sys.stderr)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written += 1

    print(f"  {written:,} files written to {args.out}")
    if absent:
        print(f"  {absent:,} referenced paths are in no archive "
              f"(broken references exist in the client too)")
    if failed:
        print(f"  {failed:,} failed to read", file=sys.stderr)
    client.close()
    return 1 if failed else 0


# --- parser -----------------------------------------------------------------------


def add_parser(subcommands: argparse._SubParsersAction) -> None:
    client = subcommands.add_parser(
        "client", help="read the installed game client (spells, effects, sounds, assets)"
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--client", type=Path, default=None,
                        help="client directory containing Data/ (default: autodetect)")
    common.add_argument("--index", type=Path, default=DEFAULT_INDEX,
                        help=f"cached archive index (default: {DEFAULT_INDEX})")
    common.add_argument("--reindex", action="store_true",
                        help="rebuild the archive index; needed after the launcher patches")

    verbs = client.add_subparsers(dest="client_command", required=True)

    inventory = verbs.add_parser("inventory", parents=[common],
                                 help="list archives, their contents and contested paths")
    inventory.add_argument("--out", type=Path, default=None, help="also write JSON here")
    inventory.set_defaults(func=run_inventory)

    dump = verbs.add_parser("dump-dbc", parents=[common],
                            help="decode client tables to JSON")
    dump.add_argument("tables", nargs="*", metavar="TABLE",
                      help=f"tables to dump (default: all of {', '.join(sorted(schema.TABLES))})")
    dump.add_argument("--out", type=Path, default=Path("data/client/dbc"))
    dump.set_defaults(func=run_dump_dbc)

    effects = verbs.add_parser(
        "effects", parents=[common],
        help="join spells to the models and sounds the client plays for them",
    )
    effects.add_argument("--dataset", type=Path, default=None,
                         help="scraped talent dataset to take spell ids from, "
                              "e.g. data/voljin/stormbringer")
    effects.add_argument("--spell", type=int, action="append",
                         help="an extra spell id (repeatable)")
    effects.add_argument("--out", type=Path, default=Path("data/client/effects.json"))
    effects.set_defaults(func=run_effects)

    extract = verbs.add_parser("extract", parents=[common],
                               help="write asset files out of the archives")
    extract.add_argument("path", nargs="*", help="in-archive path (repeatable)")
    extract.add_argument("--from-effects", type=Path, default=None,
                         help="extract every model and sound named by an effects.json")
    extract.add_argument("--icons", action="store_true",
                         help="also extract spell icon textures")
    extract.add_argument("--out", type=Path, default=Path("data/client/assets"))
    extract.add_argument("--overwrite", action="store_true")
    extract.add_argument("--verbose", action="store_true")
    extract.set_defaults(func=run_extract)
