"""Patch-chain ordering, which decides which archive wins a duplicated path."""

from __future__ import annotations

import pytest

from ascension_coa_scraper.client.install import Chain, Install, InstallError, find_install


def _make_install(tmp_path, archives, locales=(), realms=None):
    data = tmp_path / "Data"
    data.mkdir()
    for name in archives:
        (data / name).write_bytes(b"")
    for locale in locales:
        (data / locale).mkdir()
        (data / locale / f"locale-{locale}.MPQ").write_bytes(b"")
    for realm, declared in (realms or {}).items():
        (data / realm).mkdir()
        (data / realm / "listarchive").write_text("\n".join(declared))
        for name in declared:
            (data / realm / name).write_bytes(b"")
    return Install(tmp_path)


def test_base_archives_load_in_blizzards_fixed_order(tmp_path):
    install = _make_install(tmp_path, ["patch-3.MPQ", "common.MPQ", "expansion.MPQ"])
    order = [a.name for a in install.chain().archives]
    assert order == ["common.MPQ", "expansion.MPQ", "patch-3.MPQ"]


def test_shorter_suffixes_load_before_longer_ones(tmp_path):
    # The rule vanilla does not define: Ascension adds multi-character suffixes, and
    # patch-CHA must load after patch-CA, which must load after patch-A.
    install = _make_install(tmp_path, ["patch-CHA.MPQ", "patch-A.MPQ", "patch-CA.MPQ"])
    order = [a.name for a in install.chain().archives]
    assert order == ["patch-A.MPQ", "patch-CA.MPQ", "patch-CHA.MPQ"]


def test_numeric_suffixes_load_before_alphabetic_ones(tmp_path):
    install = _make_install(tmp_path, ["patch-A.MPQ", "patch-4.MPQ"])
    assert [a.name for a in install.chain().archives] == ["patch-4.MPQ", "patch-A.MPQ"]


def test_lowercase_mpq_extension_is_still_a_patch(tmp_path):
    # patch-P.mpq ships lowercase in a real install.
    install = _make_install(tmp_path, ["patch-P.mpq"])
    assert [a.name for a in install.chain().archives] == ["patch-P.mpq"]


def test_realm_archives_load_last(tmp_path):
    install = _make_install(
        tmp_path, ["patch-T.MPQ"], locales=["enUS"], realms={"area-52": ["patch-D.MPQ"]}
    )
    chain = install.chain()
    assert [a.name for a in chain.archives] == [
        "locale-enUS.MPQ", "patch-T.MPQ", "patch-D.MPQ",
    ]
    assert [a.role for a in chain.archives] == ["locale", "custom", "realm"]


def test_locale_archives_load_after_base_and_before_custom(tmp_path):
    install = _make_install(tmp_path, ["common.MPQ", "patch-A.MPQ"], locales=["enUS"])
    assert [a.role for a in install.chain().archives] == ["base", "locale", "custom"]


def test_winner_is_the_last_archive_to_provide_a_path():
    chain = Chain(archives=[])
    chain.providers = {"dbfilesclient\\spell.dbc": ["patch-T.MPQ", "patch-D.MPQ"]}
    assert chain.winner("DBFilesClient/Spell.dbc") == "patch-D.MPQ"
    assert chain.winner("DBFilesClient/Missing.dbc") is None


def test_conflicts_lists_only_duplicated_paths():
    chain = Chain(archives=[])
    chain.providers = {
        "a\\one.dbc": ["patch-S.MPQ"],
        "a\\two.dbc": ["patch-S.MPQ", "patch-T.MPQ"],
    }
    assert chain.conflicts == {"a\\two.dbc": ["patch-S.MPQ", "patch-T.MPQ"]}


def test_explicit_path_without_data_dir_is_rejected(tmp_path):
    with pytest.raises(InstallError, match="no Data/"):
        find_install(tmp_path)
