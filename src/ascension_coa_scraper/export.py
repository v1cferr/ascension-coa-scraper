"""Write a normalized dataset to disk.

Layout, one directory per class::

    data/stormbringer/
    |-- stormbringer.json   index: metadata, class info, pointers to the trees
    |-- class.json          the shared baseline tab
    |-- lightning.json
    |-- wind.json
    |-- maelstrom.json
    `-- assets/icons/*.webp only with --download-assets

Each tree file repeats the metadata and class info so it stands on its own; a consumer
that only wants one tree never has to read the index.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import ClassDataset, ClassIndex, TreeFile, TreeRef

INDEX_SUFFIX = ".json"


@dataclass
class ExportResult:
    """What a write produced, for reporting back to the user."""

    directory: Path
    index_path: Path
    tree_paths: list[Path] = field(default_factory=list)
    asset_paths: list[Path] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return 1 + len(self.tree_paths) + len(self.asset_paths)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8")


def tree_filenames(dataset: ClassDataset) -> dict[int, str]:
    """Pick a filename per tree, keeping them unique and clear of the index file.

    Tree slugs come from upstream tab names, so collisions are possible in principle
    (two tabs named the same, or a tab named after its class). Falling back to the tab
    id keeps the output deterministic instead of silently overwriting a file.
    """
    index_name = f"{dataset.class_info.slug}{INDEX_SUFFIX}"
    names: dict[int, str] = {}
    used = {index_name}

    for tree in dataset.trees:
        base = tree.slug or f"tab-{tree.id}"
        candidate = f"{base}{INDEX_SUFFIX}"
        if candidate in used:
            candidate = f"{base}-{tree.id}{INDEX_SUFFIX}"
        used.add(candidate)
        names[tree.id] = candidate

    return names


def write_dataset(dataset: ClassDataset, out_dir: Path) -> ExportResult:
    """Write a class dataset under ``out_dir/<class-slug>/`` and report the files."""
    directory = out_dir / dataset.class_info.slug
    directory.mkdir(parents=True, exist_ok=True)

    filenames = tree_filenames(dataset)
    tree_paths: list[Path] = []
    refs: list[TreeRef] = []

    for tree in dataset.trees:
        filename = filenames[tree.id]
        payload = TreeFile(
            meta=dataset.meta,
            **{"class": dataset.class_info},
            tree=tree,
        )
        path = directory / filename
        _write_json(path, payload.model_dump(mode="json", by_alias=True))
        tree_paths.append(path)

        refs.append(
            TreeRef(
                id=tree.id,
                name=tree.name,
                slug=tree.slug,
                sort_order=tree.sort_order,
                is_shared=tree.is_shared,
                talent_count=tree.talent_count,
                file=filename,
            )
        )

    index_path = directory / f"{dataset.class_info.slug}{INDEX_SUFFIX}"
    index = ClassIndex(meta=dataset.meta, **{"class": dataset.class_info}, trees=refs)
    _write_json(index_path, index.model_dump(mode="json", by_alias=True))

    return ExportResult(directory=directory, index_path=index_path, tree_paths=tree_paths)
