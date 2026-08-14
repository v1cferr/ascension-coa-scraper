"""Per-class presentation metadata that lives in the JS bundle, not in the page payload.

The talent payload gives each class an id and a display name, but the class emblem and
theme colour come from a lookup table compiled into the builder's JavaScript::

    let w={12:{classFile:"barbarian",color:"rgb(138, 51, 3)",rgb:"138, 51, 3"},...}

``classFile`` is the sprite key for the class emblem (``.coa-builder-icon.class-<file>``)
and is *not* derivable from the display name -- several classes were renamed while their
internal file kept the old name (Felsworn is still ``demonhunter``, Templar is ``monk``).

Because it is compiled into a bundle rather than served as data, it is mirrored here.
:func:`ascension_coa_scraper.cli` warns when the scraped payload contains a class id that
is missing from this table, which is the signal to re-derive it -- see
``docs/DATA_SOURCE.md``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassMeta:
    """Presentation metadata for one class."""

    class_file: str
    color: str


# Keyed by upstream classId. Derived from the builder bundle on 2026-08-13.
CLASS_META: dict[int, ClassMeta] = {
    12: ClassMeta("barbarian", "rgb(138, 51, 3)"),
    13: ClassMeta("witchdoctor", "rgb(245, 0, 255)"),
    14: ClassMeta("demonhunter", "rgb(117, 250, 0)"),
    15: ClassMeta("witchhunter", "rgb(84, 51, 207)"),
    16: ClassMeta("stormbringer", "rgb(0, 125, 237)"),
    17: ClassMeta("fleshwarden", "rgb(252, 0, 5)"),
    18: ClassMeta("guardian", "rgb(156, 148, 130)"),
    19: ClassMeta("monk", "rgb(255, 250, 179)"),
    20: ClassMeta("sonofarugal", "rgb(163, 0, 0)"),
    21: ClassMeta("ranger", "rgb(191, 240, 107)"),
    22: ClassMeta("chronomancer", "rgb(255, 237, 74)"),
    23: ClassMeta("necromancer", "rgb(69, 219, 156)"),
    24: ClassMeta("pyromancer", "rgb(255, 97, 18)"),
    25: ClassMeta("cultist", "rgb(156, 69, 242)"),
    26: ClassMeta("starcaller", "rgb(143, 255, 255)"),
    27: ClassMeta("suncleric", "rgb(255, 179, 64)"),
    28: ClassMeta("tinker", "rgb(217, 217, 217)"),
    29: ClassMeta("prophet", "rgb(107, 166, 0)"),
    30: ClassMeta("reaper", "rgb(10, 135, 107)"),
    31: ClassMeta("wildwalker", "rgb(227, 140, 89)"),
    32: ClassMeta("spiritmage", "rgb(64, 199, 235)"),
}


def get(class_id: int) -> ClassMeta | None:
    return CLASS_META.get(class_id)
