"""The normalized dataset schema.

This is deliberately *our* shape, not the builder's. Consumers code against these
models; when Ascension renames a field or restructures its payload, the change is
absorbed in `normalize.py` and this schema stays stable.

Naming differences from upstream worth knowing:

- upstream ``teCost`` / ``aeCost``  -> ``costs.talent_essence`` / ``costs.ability_essence``
- upstream ``reqTabTE`` / ``reqTabAE`` -> ``requirements.tree_talent_essence`` / ``...``
- upstream ``maxPoints``            -> ``max_ranks``
- upstream ``connectedNodeIds``     -> ``connections`` (zero padding removed)
- upstream ``group``                -> ``choice_group`` (0 becomes ``None``)
- upstream ``entriesByTab``         -> talents grouped into :class:`TalentTree`
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# The tab shared by every class in the builder; it holds baseline, non-spec talents.
SHARED_CLASS_TAB_ID = 87


class Model(BaseModel):
    """Base model: forbids unknown fields so upstream additions surface in tests."""

    model_config = {"extra": "forbid", "populate_by_name": True}


class EntryType(StrEnum):
    TALENT = "talent"
    ABILITY = "ability"


class NodeShape(StrEnum):
    """Shape the builder draws for a node. Cosmetic upstream, but a useful grouping."""

    CIRCLE = "circle"
    SQUARE = "square"
    HEX = "hex"
    UNKNOWN = "unknown"


class SpriteRef(Model):
    """Where an icon lives inside the builder's sprite sheet.

    The builder has no per-icon URLs: every icon is one cell of a single sheet,
    addressed by CSS ``background-position``. We record the sheet plus integer cell
    coordinates so an icon can be sliced out deterministically.
    """

    sheet_url: str = Field(description="Absolute URL of the sprite sheet image")
    column: int = Field(description="Zero-based cell column within the sheet")
    row: int = Field(description="Zero-based cell row within the sheet")
    columns: int = Field(description="Total cells per row in the sheet")
    rows: int = Field(description="Total cells per column in the sheet")


class Icon(Model):
    """An icon reference, resolved as far as the source allows."""

    source_path: str = Field(description="Raw game path, e.g. 'Interface\\\\Icons\\\\ability_x'")
    key: str = Field(description="Normalized icon name, matching the sprite CSS class")
    sprite: SpriteRef | None = Field(
        default=None, description="Sheet coordinates; null when the icon is not in the sheet"
    )
    file: str | None = Field(
        default=None, description="Dataset-relative path, set only when assets are downloaded"
    )


class Position(Model):
    """Node placement inside its tree grid, as authored upstream."""

    x: float
    y: float


class Costs(Model):
    talent_essence: int = 0
    ability_essence: int = 0


class Requirements(Model):
    """What must be true before a node can be taken."""

    tree_talent_essence: int = Field(
        default=0, description="Talent essence that must already be spent in this tree"
    )
    tree_ability_essence: int = Field(
        default=0, description="Ability essence that must already be spent in this tree"
    )
    level: int = Field(default=0, description="Character level requirement; 0 when none")
    talent_ids: list[int] = Field(
        default_factory=list, description="Prerequisite node ids (upstream 'requiredIds')"
    )


class TalentRank(Model):
    """One rank of a talent, with the tooltip the builder pre-renders for it."""

    rank: int
    spell_id: int | None = None
    description_html: str = ""
    description: str = Field(default="", description="Plain-text rendering of description_html")


class Talent(Model):
    """A single node in a talent tree."""

    id: int = Field(description="Upstream node id, unique within a realm dataset")
    name: str
    slug: str
    entry_type: EntryType
    node_shape: NodeShape
    is_passive: bool = False
    is_starting_node: bool = False
    max_ranks: int = 1

    class_id: int
    tree_id: int = Field(description="Upstream tabId this node belongs to")

    position: Position
    costs: Costs
    requirements: Requirements

    spell_id: int | None = None
    spell_ids: list[int] = Field(default_factory=list)

    description_html: str = ""
    description: str = Field(default="", description="Plain-text rendering of description_html")
    ranks: list[TalentRank] = Field(default_factory=list)

    connections: list[int] = Field(
        default_factory=list, description="Node ids this node links to in the tree graph"
    )
    choice_group: int | None = Field(
        default=None, description="Shared id for mutually exclusive choice nodes"
    )

    icon: Icon
    sort_order: int = 0
    flags: int = Field(default=0, description="Opaque upstream bitfield, preserved verbatim")


class TalentTree(Model):
    """One specialization tree (upstream: a 'tab')."""

    id: int = Field(description="Upstream tabId")
    name: str
    slug: str
    sort_order: int = 0
    class_id: int
    is_shared: bool = Field(
        default=False, description="True for the baseline 'Class' tab shared by all classes"
    )
    talents: list[Talent] = Field(default_factory=list)

    @property
    def talent_count(self) -> int:
        return len(self.talents)


class TreeRef(Model):
    """Pointer from the class index file to a tree file."""

    id: int
    name: str
    slug: str
    sort_order: int
    is_shared: bool
    talent_count: int
    file: str = Field(description="Dataset-relative path to the tree's JSON file")


class RealmRef(Model):
    id: int | None = None
    slug: str = ""
    name: str = ""


class ExtractionMeta(Model):
    """Provenance for a dataset, so runs can be compared and reproduced."""

    source: str = Field(description="Absolute URL the data was extracted from")
    builder: str = Field(default="coa", description="Which Ascension builder was scraped")
    realm: RealmRef
    scraped_at: str = Field(description="UTC ISO-8601 timestamp of the extraction")
    schema_version: int = Field(description="Version of this project's normalized schema")
    scraper_version: str
    upstream_schema_version: dict[str, int] | None = Field(
        default=None, description="The site's own schema_version field, preserved as-is"
    )
    content_hash: str = Field(
        description="SHA-256 over the normalized talent data; changes when the trees change"
    )
    talent_count: int = 0
    tree_count: int = 0


class ClassInfo(Model):
    id: int
    name: str
    slug: str
    max_talent_essence: int | None = None
    max_ability_essence: int | None = None
    icon: Icon | None = Field(
        default=None, description="Class emblem from the sprite sheet, when available"
    )


class ClassDataset(Model):
    """Everything extracted for one class: the index file plus its trees in memory."""

    meta: ExtractionMeta
    class_info: ClassInfo = Field(alias="class")
    trees: list[TalentTree] = Field(default_factory=list)


class ClassIndex(Model):
    """What gets written to ``<class>/<class>.json``: metadata and pointers to trees."""

    meta: ExtractionMeta
    class_info: ClassInfo = Field(alias="class")
    trees: list[TreeRef] = Field(default_factory=list)


class TreeFile(Model):
    """What gets written to ``<class>/<tree>.json``."""

    meta: ExtractionMeta
    class_info: ClassInfo = Field(alias="class")
    tree: TalentTree
