import json

from ascension_coa_scraper.export import tree_filenames, write_dataset
from ascension_coa_scraper.models import (
    ClassDataset,
    ClassInfo,
    Costs,
    ExtractionMeta,
    Icon,
    Position,
    RealmRef,
    Requirements,
    Talent,
    TalentTree,
)


def _talent(talent_id: int, name: str, tree_id: int) -> Talent:
    return Talent(
        id=talent_id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        entry_type="talent",
        node_shape="circle",
        class_id=16,
        tree_id=tree_id,
        position=Position(x=0, y=0),
        costs=Costs(),
        requirements=Requirements(),
        icon=Icon(source_path="Interface\\Icons\\x", key="x"),
    )


def _dataset(trees: list[TalentTree]) -> ClassDataset:
    meta = ExtractionMeta(
        source="https://ascension.gg/en/v2/coa-builder/voljin",
        realm=RealmRef(id=40, slug="voljin", name="Vol'Jin"),
        scraped_at="2026-08-13T12:00:00+00:00",
        schema_version=1,
        scraper_version="0.1.0",
        content_hash="sha256:abc",
        talent_count=sum(len(t.talents) for t in trees),
        tree_count=len(trees),
    )
    info = ClassInfo(id=16, name="Stormbringer", slug="stormbringer")
    return ClassDataset(meta=meta, **{"class": info}, trees=trees)


def _sample() -> ClassDataset:
    return _dataset(
        [
            TalentTree(
                id=87,
                name="Class",
                slug="class",
                sort_order=0,
                class_id=16,
                is_shared=True,
                talents=[_talent(1, "Base", 87)],
            ),
            TalentTree(
                id=42,
                name="Lightning",
                slug="lightning",
                sort_order=1,
                class_id=16,
                talents=[_talent(2, "Lightning Rod", 42), _talent(3, "Volt", 42)],
            ),
        ]
    )


def test_write_dataset_creates_an_index_and_one_file_per_tree(tmp_path):
    result = write_dataset(_sample(), tmp_path)

    assert result.directory == tmp_path / "stormbringer"
    assert result.index_path.name == "stormbringer.json"
    assert sorted(p.name for p in result.tree_paths) == ["class.json", "lightning.json"]


def test_index_points_at_the_tree_files_with_counts(tmp_path):
    write_dataset(_sample(), tmp_path)

    index = json.loads((tmp_path / "stormbringer" / "stormbringer.json").read_text())

    assert index["class"]["slug"] == "stormbringer"
    assert [t["file"] for t in index["trees"]] == ["class.json", "lightning.json"]
    assert [t["talent_count"] for t in index["trees"]] == [1, 2]
    assert index["trees"][0]["is_shared"] is True


def test_tree_files_are_self_contained(tmp_path):
    write_dataset(_sample(), tmp_path)

    tree = json.loads((tmp_path / "stormbringer" / "lightning.json").read_text())

    assert tree["meta"]["content_hash"] == "sha256:abc"
    assert tree["class"]["name"] == "Stormbringer"
    assert [t["name"] for t in tree["tree"]["talents"]] == ["Lightning Rod", "Volt"]


def test_index_uses_the_class_alias_not_the_python_field_name(tmp_path):
    write_dataset(_sample(), tmp_path)

    index = json.loads((tmp_path / "stormbringer" / "stormbringer.json").read_text())

    assert "class" in index
    assert "class_info" not in index


def test_tree_filenames_avoid_colliding_with_the_index():
    # A tab named after its own class would otherwise overwrite the index file.
    dataset = _dataset(
        [TalentTree(id=42, name="Stormbringer", slug="stormbringer", class_id=16, talents=[])]
    )

    assert tree_filenames(dataset) == {42: "stormbringer-42.json"}


def test_tree_filenames_disambiguate_duplicate_slugs():
    dataset = _dataset(
        [
            TalentTree(id=1, name="None", slug="none", class_id=16, talents=[]),
            TalentTree(id=2, name="None", slug="none", class_id=16, talents=[]),
        ]
    )

    assert tree_filenames(dataset) == {1: "none.json", 2: "none-2.json"}


def test_tree_filenames_fall_back_to_the_tab_id_when_a_name_has_no_slug():
    dataset = _dataset([TalentTree(id=44, name="???", slug="", class_id=16, talents=[])])

    assert tree_filenames(dataset) == {44: "tab-44.json"}


def test_write_dataset_output_is_stable_across_runs(tmp_path):
    write_dataset(_sample(), tmp_path)
    first = (tmp_path / "stormbringer" / "lightning.json").read_bytes()

    write_dataset(_sample(), tmp_path)
    second = (tmp_path / "stormbringer" / "lightning.json").read_bytes()

    assert first == second
