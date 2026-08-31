"""Command-line entry point.

    ascension-coa scrape stormbringer [--download-assets]
    ascension-coa list-classes
    ascension-coa client inventory
    ascension-coa client effects --dataset data/voljin/stormbringer
    ascension-coa serve --lan

`scrape` is class-agnostic: any class name, slug, or id present in the payload works, so
adding support for a new class is a matter of naming it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, classmeta
from .assets import AssetError, download_icons
from .client import commands as client_commands
from .discovery import DatasetNotFoundError, find_realms, select_realm
from .export import write_dataset
from .fetch import DEFAULT_REALM, Fetcher, FetchError
from .flight import FlightParseError, parse_html
from .icons import SpriteError, load_sprite_sheet
from .index import IndexError_, build_search
from .index import build as build_index
from .index import write as write_index
from .normalize import NormalizeError, list_classes, normalize_class
from .serve import ALL_INTERFACES, LOOPBACK, describe, serve

DEFAULT_OUT_DIR = Path("data")
DEFAULT_CACHE_DIR = Path(".cache")

# Every failure the scraper raises on purpose; anything else is a real bug and should
# keep its traceback.
_EXPECTED_ERRORS = (
    AssetError,
    DatasetNotFoundError,
    FetchError,
    FlightParseError,
    NormalizeError,
    SpriteError,
    IndexError_,
    *client_commands.CLIENT_ERRORS,
)


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ascension-coa",
        description="Extract Conquest of Azeroth talent trees into structured JSON.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--realm",
        default=DEFAULT_REALM,
        help=f"realm slug used in the builder URL (default: {DEFAULT_REALM})",
    )
    common.add_argument(
        "--realm-slug",
        default=None,
        help="realm to read from the page payload, when it differs from --realm "
        "(a page lists several, e.g. 'voljin-alpha')",
    )
    common.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"directory for cached HTTP responses (default: {DEFAULT_CACHE_DIR})",
    )
    common.add_argument(
        "--no-cache",
        action="store_true",
        help="always re-download instead of reusing the cache",
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    scrape = subcommands.add_parser(
        "scrape", parents=[common], help="extract one class into a JSON dataset"
    )
    scrape.add_argument("class_name", metavar="CLASS", help="class name, slug, or numeric id")
    scrape.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"output directory (default: {DEFAULT_OUT_DIR})",
    )
    scrape.add_argument(
        "--download-assets",
        action="store_true",
        help="also slice this class's icons out of the sprite sheet (needs the 'assets' extra)",
    )

    subcommands.add_parser(
        "list-classes", parents=[common], help="list the classes available in a realm"
    )

    index = subcommands.add_parser(
        "build-index", help="write the manifest the web viewer reads"
    )
    index.add_argument(
        "--data", type=Path, default=DEFAULT_OUT_DIR,
        help=f"directory of <realm>/<class>/ datasets (default: {DEFAULT_OUT_DIR})",
    )
    index.add_argument(
        "--effects", type=Path, default=Path("data/client/effects"),
        help="directory of resolved effects JSON",
    )
    index.add_argument("--sprite-sheet", type=Path,
                       default=Path("data/_assets/coa-builder-icon.webp"),
                       help="icon sprite sheet the talent data addresses by cell")
    index.add_argument("--out", type=Path, default=Path("data/index.json"))

    viewer = subcommands.add_parser(
        "serve", help="serve the repository so the viewer can read its datasets"
    )
    viewer.add_argument("--port", type=int, default=8000)
    viewer.add_argument(
        "--root", type=Path, default=Path("."),
        help="directory to serve (default: the current one, which should hold web/ and data/)",
    )
    binding = viewer.add_mutually_exclusive_group()
    binding.add_argument(
        "--lan", action="store_true",
        help="bind every interface so other machines on the network can reach it; "
             "the default is loopback only",
    )
    binding.add_argument("--host", default=None, help="bind one specific address")

    client_commands.add_parser(subcommands)

    return parser


def _open_realm(args: argparse.Namespace, fetcher: Fetcher):
    """Fetch the builder page and return ``(html, realm, source_url)``."""
    source_url = fetcher.builder_url(args.realm)
    html = fetcher.builder_page(args.realm)
    realms = find_realms(parse_html(html))
    realm = select_realm(realms, args.realm_slug or args.realm)
    return html, realm, source_url


def _run_list_classes(args: argparse.Namespace, fetcher: Fetcher) -> int:
    _, realm, _ = _open_realm(args, fetcher)

    print(f"{realm.name} ({realm.slug})")
    for class_id, name, slug in sorted(list_classes(realm), key=lambda row: row[1]):
        print(f"  {class_id:>3}  {slug:<18} {name}")
    return 0


def _run_scrape(args: argparse.Namespace, fetcher: Fetcher) -> int:
    html, realm, source_url = _open_realm(args, fetcher)

    try:
        sheet = load_sprite_sheet(fetcher, html)
    except (SpriteError, FetchError) as exc:
        # Icons are a bonus; a dataset without sprite coordinates is still useful.
        _warn(f"could not resolve the icon sprite sheet ({exc}); icons will have no coordinates")
        sheet = None

    dataset = normalize_class(realm, args.class_name, source_url, sheet)

    if classmeta.get(dataset.class_info.id) is None:
        _warn(
            f"no bundled metadata for class id {dataset.class_info.id} "
            f"({dataset.class_info.name}); emblem and colour are missing — "
            "see docs/DATA_SOURCE.md to refresh classmeta.py"
        )

    assets: list[Path] = []
    if args.download_assets:
        assets = download_icons(dataset, fetcher, args.out / dataset.class_info.slug)

    result = write_dataset(dataset, args.out)
    result.asset_paths = assets

    print(f"{dataset.class_info.name} -> {result.directory}")
    for tree in dataset.trees:
        print(f"  {tree.slug:<12} {tree.talent_count:>3} talents")
    print(
        f"  {dataset.meta.talent_count} talents in {dataset.meta.tree_count} trees"
        f"{f', {len(assets)} icons' if args.download_assets else ''}"
    )
    print(f"  {dataset.meta.content_hash}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # The client subcommands read local archives; they need no HTTP session, and
    # building one would make an offline run fail for no reason.
    if args.command == "serve":
        root = args.root.resolve()
        if not (root / "web").is_dir():
            _warn(f"{root} has no web/ directory; the viewer will 404")
        host = args.host or (ALL_INTERFACES if args.lan else LOOPBACK)
        try:
            httpd = serve(root, host=host, port=args.port)
        except OSError as exc:
            print(f"error: cannot bind {host}:{args.port} ({exc})", file=sys.stderr)
            return 1
        for line in describe(host, args.port, root):
            print(line)
        # The address is the whole point of the command and the process then blocks,
        # so it has to leave the buffer now; piped output would otherwise show nothing.
        print("\nCtrl-C to stop.", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()
        finally:
            httpd.server_close()
        return 0

    if args.command == "build-index":
        try:
            index = build_index(
                args.data, effects_dir=args.effects, sprite_sheet=args.sprite_sheet,
                asset_root=Path("data/client/assets"),
            )
            path = write_index(index, args.out)
            search = build_search(index, args.data)
            search_path = args.out.with_name("search.json")
            search_path.write_text(
                json.dumps(search, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
        except _EXPECTED_ERRORS as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        classes = sum(len(r.classes) for r in index.realms)
        with_effects = sum(1 for r in index.realms for c in r.classes if c.effects_file)
        print(f"{len(index.realms)} realms, {classes} class datasets "
              f"({with_effects} with effects) -> {path}")
        print(f"{len(search['rows']):,} talents indexed for search -> {search_path}")
        if index.sprite_sheet is None:
            _warn("no icon sprite sheet found; the viewer will show placeholders")
        return 0

    if args.command == "client":
        try:
            return args.func(args)
        except _EXPECTED_ERRORS as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    cache_dir = None if args.no_cache else args.cache_dir

    try:
        with Fetcher(cache_dir=cache_dir) as fetcher:
            if args.command == "list-classes":
                return _run_list_classes(args, fetcher)
            return _run_scrape(args, fetcher)
    except _EXPECTED_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
