"""Resolve talent icons against the builder's CSS sprite sheet.

The builder never exposes a URL per icon. Each entry carries a game path such as
``Interface\\Icons\\inv_rod_enchantedcobalt``; the frontend reduces that to a CSS class
and renders ``<span class="coa-builder-icon inv_rod_enchantedcobalt">``. A stylesheet
maps every class to one cell of a single sheet::

    .coa-builder-icon{background:url(/icon/coa-builder-icon.webp) 50% no-repeat;...}
    .coa-builder-icon.inv_rod_enchantedcobalt{background-position:1.85185% 0;
                                              background-size:5500%,5500%}

With CSS percentage positioning, a sheet of ``N`` columns places cell ``i`` at
``i / (N - 1) * 100%``, and ``background-size: N*100%`` is what sets ``N``. Inverting
that gives integer cell coordinates, which is what we store and what asset extraction
uses to slice the sheet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .fetch import Fetcher

SPRITE_BASE_CLASS = "coa-builder-icon"
FALLBACK_ICON_KEY = "inv_misc_questionmark"

_CSS_LINK_RE = re.compile(r'href="(/_next/static/chunks/[^"]+\.css)"')
_BASE_RULE_RE = re.compile(
    rf"\.{SPRITE_BASE_CLASS}\{{[^}}]*?url\((?P<url>[^)]+)\)", re.IGNORECASE
)
_CELL_RULE_RE = re.compile(
    rf"\.{SPRITE_BASE_CLASS}\.(?P<key>[A-Za-z0-9_-]+)\{{(?P<body>[^}}]*)\}}"
)
_POSITION_RE = re.compile(
    r"background-position:\s*(?P<x>-?[\d.]+)(?P<xu>%?)\s+(?P<y>-?[\d.]+)(?P<yu>%?)"
)
_SIZE_RE = re.compile(r"background-size:\s*(?P<size>[\d.]+)%")

# Matches the site's own icon-name normalization (function `eO` in the builder bundle).
_ICON_EXT_RE = re.compile(r"\.(blp|png|tga|jpg|jpeg)$", re.IGNORECASE)
_ICON_SAFE_RE = re.compile(r"[^a-z0-9_-]+")


class SpriteError(RuntimeError):
    """Raised when the sprite sheet cannot be located or parsed."""


def icon_key(icon_path: str | None) -> str:
    """Reduce a game icon path to the CSS class the builder uses for it.

    Mirrors the frontend's own normalization: take the last non-empty path segment,
    drop a known image extension, lowercase, replace unsafe runs with ``_``, trim
    underscores, and prefix a leading digit with ``_`` so the result is a valid CSS
    identifier.

    One deliberate difference: where the site yields ``null`` for a missing path, we
    return :data:`FALLBACK_ICON_KEY` so the normalized schema never carries an empty key.
    """
    if not icon_path:
        return FALLBACK_ICON_KEY

    basename = next(
        (part for part in reversed(re.split(r"[\\/]", icon_path)) if part),
        "",
    )
    stem = _ICON_EXT_RE.sub("", basename).lower()
    if not stem:
        return FALLBACK_ICON_KEY

    safe = _ICON_SAFE_RE.sub("_", stem).strip("_")
    if not safe:
        return FALLBACK_ICON_KEY
    return f"_{safe}" if safe[0].isdigit() else safe


def class_icon_key(class_file: str) -> str:
    """Sprite key for a class emblem, e.g. 'stormbringer' -> 'class-stormbringer'.

    Takes the upstream ``classFile`` (see :mod:`ascension_coa_scraper.classmeta`), not the
    display name: renamed classes kept their original file, so 'Templar' is 'monk'.
    """
    return f"class-{class_file}"


@dataclass(frozen=True)
class SpriteSheet:
    """A parsed sprite sheet: its URL, its grid size, and every cell it defines."""

    url: str
    columns: int
    rows: int
    cells: dict[str, tuple[int, int]]

    def locate(self, key: str) -> tuple[int, int] | None:
        """Return ``(column, row)`` for an icon key, or ``None`` when absent."""
        return self.cells.get(key)


def find_sprite_css_urls(html: str) -> list[str]:
    """Return the stylesheet paths linked by a builder page, in document order."""
    seen: list[str] = []
    for match in _CSS_LINK_RE.finditer(html):
        path = match.group(1)
        if path not in seen:
            seen.append(path)
    return seen


def parse_sprite_css(css: str, resolve_url) -> SpriteSheet:
    """Parse sprite rules out of a stylesheet.

    Args:
        css: Stylesheet text.
        resolve_url: Callable turning the sheet's (possibly relative) URL into an
            absolute one.

    Raises:
        SpriteError: if the stylesheet has no usable sprite rules.
    """
    base = _BASE_RULE_RE.search(css)
    if base is None:
        raise SpriteError(f"no .{SPRITE_BASE_CLASS} background rule found in stylesheet")
    sheet_url = resolve_url(base.group("url").strip("'\""))

    columns = 0
    cells: dict[str, tuple[int, int]] = {}

    for rule in _CELL_RULE_RE.finditer(css):
        body = rule.group("body")
        position = _POSITION_RE.search(body)
        size = _SIZE_RE.search(body)
        if position is None or size is None:
            continue

        grid = round(float(size.group("size")) / 100)
        if grid < 2:
            continue
        columns = max(columns, grid)

        # A bare `0` is unitless in the CSS, but zero percent is still zero.
        x_pct = float(position.group("x"))
        y_pct = float(position.group("y"))
        cells[rule.group("key")] = (
            round(x_pct * (grid - 1) / 100),
            round(y_pct * (grid - 1) / 100),
        )

    if not cells:
        raise SpriteError(f"no .{SPRITE_BASE_CLASS}.<key> cell rules found in stylesheet")

    # The builder's sheet is square; asset extraction re-derives the true row count from
    # the downloaded image, so this is only a metadata-time assumption.
    return SpriteSheet(url=sheet_url, columns=columns, rows=columns, cells=cells)


def load_sprite_sheet(fetcher: Fetcher, html: str) -> SpriteSheet:
    """Find and parse the builder's sprite stylesheet, given a fetched page.

    Raises:
        SpriteError: if none of the page's stylesheets define sprite rules.
    """
    for path in find_sprite_css_urls(html):
        css = fetcher.get_text(path)
        if SPRITE_BASE_CLASS not in css:
            continue
        return parse_sprite_css(css, fetcher.resolve)

    raise SpriteError(
        "no stylesheet on the page defines .coa-builder-icon rules; "
        "re-run the discovery steps in docs/DATA_SOURCE.md"
    )
