import pytest

from ascension_coa_scraper.classmeta import CLASS_META
from ascension_coa_scraper.icons import (
    FALLBACK_ICON_KEY,
    SpriteError,
    class_icon_key,
    find_sprite_css_urls,
    icon_key,
    parse_sprite_css,
)

CSS = """
.coa-builder-icon{background:url(/icon/coa-builder-icon.webp) 50% no-repeat;width:100%}
.coa-builder-icon._5_archerskill01{background-position:0 0;background-size:5500%,5500%}
.coa-builder-icon.inv_rod_enchantedcobalt{background-position:1.85185% 0;\
background-size:5500%,5500%}
.coa-builder-icon.class-barbarian{background-position:51.8519% 100%;background-size:5500%,5500%}
"""


def _resolve(url: str) -> str:
    return url if url.startswith("http") else f"https://ascension.gg{url}"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("Interface\\Icons\\inv_rod_enchantedcobalt", "inv_rod_enchantedcobalt"),
        ("Interface/Icons/ability_warrior_shieldguard", "ability_warrior_shieldguard"),
        ("Interface\\Icons\\INV_Sword_04.blp", "inv_sword_04"),
        ("spell-fire.png", "spell-fire"),
        # A leading digit is not a valid CSS identifier start, so the site prefixes '_'.
        ("Interface\\Icons\\5_archerskill01", "_5_archerskill01"),
        ("Interface\\Icons\\some icon!!", "some_icon"),
        # Trailing separators are dropped, so the last real segment wins -- the site
        # behaves the same way.
        ("Interface\\Icons\\", "icons"),
        # Sanitizing wipes these out entirely, which is what the fallback is for.
        ("!!!", FALLBACK_ICON_KEY),
        ("___", FALLBACK_ICON_KEY),
        # The site returns null here; we return the fallback so the field is never empty.
        ("", FALLBACK_ICON_KEY),
        (None, FALLBACK_ICON_KEY),
    ],
)
def test_icon_key_matches_the_builders_normalization(path, expected):
    assert icon_key(path) == expected


def test_class_icon_key_uses_the_upstream_class_file():
    assert class_icon_key("stormbringer") == "class-stormbringer"
    # Templar's display name changed but its sprite key did not.
    assert class_icon_key(CLASS_META[19].class_file) == "class-monk"


def test_class_meta_is_complete_and_unambiguous():
    # The builder ships 21 playable classes with ids 12..32; each needs its own sprite.
    assert len(CLASS_META) == 21
    assert set(CLASS_META) == set(range(12, 33))
    class_files = [meta.class_file for meta in CLASS_META.values()]
    assert len(set(class_files)) == len(class_files)


def test_parse_sprite_css_resolves_sheet_url_and_grid():
    sheet = parse_sprite_css(CSS, _resolve)

    assert sheet.url == "https://ascension.gg/icon/coa-builder-icon.webp"
    assert sheet.columns == 55
    assert sheet.rows == 55


def test_parse_sprite_css_inverts_percentage_positions_to_cell_indices():
    sheet = parse_sprite_css(CSS, _resolve)

    # 0% -> column 0; 1.85185% of 54 columns -> column 1; 100% -> last index (54).
    assert sheet.locate("_5_archerskill01") == (0, 0)
    assert sheet.locate("inv_rod_enchantedcobalt") == (1, 0)
    assert sheet.locate("class-barbarian") == (28, 54)


def test_parse_sprite_css_returns_none_for_unknown_icons():
    assert parse_sprite_css(CSS, _resolve).locate("does_not_exist") is None


def test_parse_sprite_css_requires_a_background_rule():
    with pytest.raises(SpriteError, match="background rule"):
        parse_sprite_css(".other{color:red}", _resolve)


def test_parse_sprite_css_requires_cell_rules():
    css = ".coa-builder-icon{background:url(/icon/sheet.webp) 50% no-repeat}"

    with pytest.raises(SpriteError, match="cell rules"):
        parse_sprite_css(css, _resolve)


def test_find_sprite_css_urls_dedupes_and_keeps_order():
    html = (
        '<link rel="stylesheet" href="/_next/static/chunks/a.css"/>'
        '<link rel="stylesheet" href="/_next/static/chunks/b.css"/>'
        '<link rel="stylesheet" href="/_next/static/chunks/a.css"/>'
    )

    assert find_sprite_css_urls(html) == [
        "/_next/static/chunks/a.css",
        "/_next/static/chunks/b.css",
    ]
