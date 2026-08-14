"""Slice individual icons out of the builder's sprite sheet.

Because the site serves one sheet rather than per-icon files, "downloading assets" means
fetching the sheet once and cropping the cells the dataset actually references. Cell
geometry is re-derived from the real image dimensions rather than trusting the CSS, so a
sheet that grows a row still slices correctly.

Requires Pillow, installed via the ``assets`` extra.
"""

from __future__ import annotations

import io
from pathlib import Path

from .fetch import Fetcher
from .models import ClassDataset, Icon

ICONS_SUBDIR = "assets/icons"
_ICON_FORMAT = "WEBP"
_ICON_EXTENSION = ".webp"


class AssetError(RuntimeError):
    """Raised when assets cannot be extracted."""


def _require_pillow():
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise AssetError(
            "downloading assets needs Pillow; install it with `uv sync --extra assets`"
        ) from exc
    return Image


def collect_icons(dataset: ClassDataset) -> dict[str, Icon]:
    """Return one icon per sprite key referenced by the dataset, class emblem included.

    Icons the sheet does not define are skipped: there is nothing to crop for them.
    """
    icons: dict[str, Icon] = {}

    if dataset.class_info.icon is not None and dataset.class_info.icon.sprite is not None:
        icons[dataset.class_info.icon.key] = dataset.class_info.icon

    for tree in dataset.trees:
        for talent in tree.talents:
            if talent.icon.sprite is not None:
                icons.setdefault(talent.icon.key, talent.icon)

    return icons


def download_icons(dataset: ClassDataset, fetcher: Fetcher, class_dir: Path) -> list[Path]:
    """Crop every referenced icon into ``<class_dir>/assets/icons`` and record the paths.

    Mutates each :class:`~ascension_coa_scraper.models.Icon` in ``dataset`` to point at
    its extracted file, so the exported JSON references local assets. Call this before
    writing the dataset.
    """
    icons = collect_icons(dataset)
    if not icons:
        return []

    image_module = _require_pillow()

    # Every icon shares one sheet; take its URL from any of them.
    sample = next(iter(icons.values()))
    assert sample.sprite is not None
    sheet_ref = sample.sprite

    sheet_bytes = fetcher.get_bytes(sheet_ref.sheet_url)
    try:
        sheet = image_module.open(io.BytesIO(sheet_bytes)).convert("RGBA")
    except OSError as exc:
        raise AssetError(f"could not decode sprite sheet {sheet_ref.sheet_url}: {exc}") from exc

    width, height = sheet.size
    if sheet_ref.columns < 1:
        raise AssetError("sprite sheet reports fewer than one column")

    cell_w = width / sheet_ref.columns
    cell_h = cell_w  # cells are square; deriving height this way tolerates extra rows.
    if cell_w < 1 or cell_h < 1:
        raise AssetError(
            f"sprite sheet {width}x{height} is too small for {sheet_ref.columns} cells"
        )

    icons_dir = class_dir / ICONS_SUBDIR
    icons_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for key, icon in sorted(icons.items()):
        sprite = icon.sprite
        assert sprite is not None

        left = round(sprite.column * cell_w)
        top = round(sprite.row * cell_h)
        if left + cell_w > width + 1 or top + cell_h > height + 1:
            # Cell lies outside the sheet we actually downloaded; leave `file` unset
            # rather than writing a blank or wrapped-around image.
            continue

        cell = sheet.crop((left, top, left + round(cell_w), top + round(cell_h)))
        path = icons_dir / f"{key}{_ICON_EXTENSION}"
        cell.save(path, _ICON_FORMAT, lossless=True)
        written.append(path)

        relative = f"{ICONS_SUBDIR}/{key}{_ICON_EXTENSION}"
        icon.file = relative

    # Talents share icon keys, so propagate the resolved path to every duplicate.
    resolved = {key: icon.file for key, icon in icons.items()}
    for tree in dataset.trees:
        for talent in tree.talents:
            if talent.icon.file is None:
                talent.icon.file = resolved.get(talent.icon.key)

    return written
