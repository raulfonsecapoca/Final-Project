from __future__ import annotations

import re
import unicodedata
from dataclasses import is_dataclass

import pytest

from pokedex.pokedex_core import PokedexAPI, PokemonEvolNode


def _flatten_evolution_tree(root: PokemonEvolNode) -> list[PokemonEvolNode]:
    """DFS flatten of the evolution tree."""
    out: list[PokemonEvolNode] = []
    stack: list[PokemonEvolNode] = [root]
    while stack:
        node = stack.pop()
        out.append(node)
        # push children
        for child in reversed(node.evolutions):
            stack.append(child)
    return out


def test_get_pokemon_pikachu_payload_matches_expected_subset() -> None:
    """
    Smoke + regression-style test for Pikachu payload.
    """
    got = PokedexAPI.get_pokemon("pikachu", language_id=9)

    assert isinstance(got, dict)
    for key in [
        "name",
        "dex_number",
        "id",
        "image",
        "cries",
        "types",
        "base_stats",
        "evolution_line",
        "forms",
        "abilities",
        "is_hidden_ability",
        "egg_groups",
    ]:
        assert key in got, f"Missing key: {key}"

    expected_subset = {
        "dex_number": 25,
        "id": 25,
        "types": [13],
        "base_stats": {
            "HP": 35,
            "Atk": 55,
            "Def": 40,
            "SpA": 50,
            "SpD": 50,
            "Spe": 90,
        },
    }

    assert int(got["dex_number"]) == expected_subset["dex_number"]

    assert isinstance(got["base_stats"], dict)
    for k in ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]:
        assert k in got["base_stats"]

    for k, v in expected_subset["base_stats"].items():
        assert int(got["base_stats"][k]) == int(v)

    assert isinstance(got["types"], list)
    assert all(isinstance(t, (int | float)) for t in got["types"])

    assert is_dataclass(got["evolution_line"])
    assert isinstance(got["evolution_line"], PokemonEvolNode)


def test_build_evolution_tree_contains_charizard_line_by_dex_numbers() -> None:
    """
    Ensure the evolution tree for the Charmander line contains (4,5,6):
    Charmander -> Charmeleon -> Charizard.

    We validate by dex numbers to avoid language-dependent name comparisons.
    """

    root = PokedexAPI.build_evolution_tree(species_id=4, language_id=9)

    nodes = _flatten_evolution_tree(root)
    dex_numbers = {int(n.dex_no) for n in nodes}

    assert {4, 5, 6}.issubset(dex_numbers)

    assert any(int(c.dex_no) == 5 for c in root.evolutions)


LANGUAGE_IDS = [i for i in range(1, 13) if i != 10]


@pytest.mark.parametrize("language_id", LANGUAGE_IDS)
def test_api_smoke_for_all_official_languages(language_id: int) -> None:
    pikachu = PokedexAPI.get_pokemon("pikachu", language_id=language_id)
    assert isinstance(pikachu, dict)
    assert isinstance(pikachu.get("name", ""), str)
    assert pikachu["name"].strip() != ""

    flavor = PokedexAPI.get_pokedex_flavor("pikachu", language_id=language_id)
    assert isinstance(flavor, dict)
    assert "versions" in flavor and "flavor_texts" in flavor
    assert isinstance(flavor["versions"], list)
    assert isinstance(flavor["flavor_texts"], list)

    types_list = PokedexAPI.get_all_types(language_id=language_id)
    assert isinstance(types_list, list)

    abilities_list = PokedexAPI.get_all_abilities(language_id=language_id)
    assert isinstance(abilities_list, list)

    evo = PokedexAPI.build_evolution_tree(species_id=4, language_id=language_id)
    nodes = _flatten_evolution_tree(evo)
    dex_numbers = {int(n.dex_no) for n in nodes}
    assert {4, 5, 6}.issubset(dex_numbers)


EXPECTED_GRENINJA_NAMES = {
    9: "Greninja",  # English fallback
    5: "Amphinobi",  # French
    6: "Quajutsu",  # German
    7: "Greninja",  # Spanish
    8: "Greninja",  # Italian
    1: "ゲッコウガ",  # Japanese
    2: "Gekkouga",  # Japanese romanized
    11: "ゲッコウガ",  # Japanese
    3: "개굴닌자",  # Korean
    4: "甲賀忍蛙",  # Chinese
    12: "甲贺忍蛙",  # Chinese
}


@pytest.mark.parametrize("language_id", LANGUAGE_IDS)
def test_greninja_name_localized_or_english_fallback(language_id: int) -> None:
    """
    For each language_id, fetch Greninja and assert that the displayed name
    matches the expected localized name. If EXPECTED_GRENINJA_NAMES does not
    include this language, English fallback (language_id=9).
    """
    payload = PokedexAPI.get_pokemon("greninja", language_id=language_id)
    got_name = str(payload.get("name", "")).strip()
    assert got_name, f"Empty name for language_id={language_id}"

    expected = EXPECTED_GRENINJA_NAMES.get(language_id, EXPECTED_GRENINJA_NAMES[9])
    assert got_name == expected, (
        f"Greninja name mismatch for language_id={language_id}. "
        f"Expected '{expected}', got '{got_name}'."
    )


EXPECTED_FIRE_STONE = {
    9: (
        "Fire Stone",
        "A peculiar stone that can make certain species of Pokémon evolve. The stone has a fiery orange heart.",
    ),  # English
    5: (
        "Pierre Feu",
        "Une pierre étrange qui fait évoluer certaines espèces de Pokémon. Elle est jaune et orange.",
    ),  # French
    6: (
        "Feuerstein",
        "Dieser spezielle Stein löst bei bestimmten Pokémon die Entwicklung aus. Er schimmert in den Farben Orange und Gelb.",
    ),  # German
    7: (
        "Piedra Fuego",
        "Curiosa piedra que hace evolucionar a determinadas especies de Pokémon. Es amarilla con una marca naranja.",
    ),  # Spanish
    8: (
        "Pietrafocaia",
        "Pietra particolare che fa evolvere determinate specie di Pokémon. È gialla e arancione.",
    ),  # Italian
    1: (
        "ほのおのいし",
        "ある　とくていの　ポケモンをしんかさせる　ふしぎな　いし。だいだいいろを　している。",
    ),  # Japanese
    11: (
        "ほのおのいし",
        "ある　特定の　ポケモンを進化させる　不思議な　石。だいだい色を　している。",
    ),  # Japanese
    3: (
        "불꽃의돌",
        "어느 특정 포켓몬을진화시키는 이상한 돌.주황색을 띠고 있다.",
    ),  # Korean
    4: ("火之石", "能讓特定寶可夢進化的神奇石頭。看起來是橙黃色的。"),  # Chinese
    12: ("火之石", "能让某些特定宝可梦进化的神奇石头。看上去是橙黄色的。"),  # Chinese
}


def _normalize_text(s: str) -> str:
    """
    Normalize text for comparison by removing all whitespace:
    - Unicode normalize (NFKC)
    - Treat U+3000 as whitespace
    - Remove any Unicode whitespace (\\s), including newlines/tabs/spaces
    """
    if s is None:
        return ""

    text = unicodedata.normalize("NFKC", str(s))

    # Make ideographic space behave like whitespace
    text = text.replace("\u3000", " ")

    # Remove ALL whitespace (spaces, tabs, newlines, etc.)
    text = re.sub(r"\s+", "", text, flags=re.UNICODE)

    return text


@pytest.mark.parametrize("language_id", LANGUAGE_IDS)
def test_fire_stone_name_and_description_by_language(language_id: int) -> None:
    """
    Fetch the same item in every language and compare name and description.
    If a language is not mapped in EXPECTED_FIRE_STONE, fallback to English.
    """
    item = PokedexAPI.get_item("Fire Stone", language_id=language_id)

    assert isinstance(item, dict)
    assert "name" in item
    assert "item_flavor_text" in item

    got_name = _normalize_text(item["name"])
    got_desc = _normalize_text(item["item_flavor_text"])

    expected_name, expected_desc = EXPECTED_FIRE_STONE.get(
        language_id, EXPECTED_FIRE_STONE[9]
    )

    assert got_name == _normalize_text(expected_name), (
        f"Fire Stone name mismatch for language_id={language_id}. "
        f"Expected '{expected_name}', got '{item['name']}'."
    )

    assert got_desc == _normalize_text(expected_desc), (
        f"Fire Stone description mismatch for language_id={language_id}. "
        f"Expected '{expected_desc}', got '{item['item_flavor_text']}'."
    )


def test_type_chart_smoke() -> None:
    """Type chart returns consistent labels/values."""
    chart = PokedexAPI.get_type_chart(language_id=9, forms_enable=False)
    assert chart.total > 0
    assert len(chart.labels) == len(chart.values)


def test_gen_chart_smoke() -> None:
    """Generation chart returns consistent labels/values."""
    chart = PokedexAPI.get_gen_chart(language_id=9, type_filter=None)
    assert chart.total > 0
    assert len(chart.labels) == len(chart.values)


def test_egg_chart_smoke() -> None:
    """Egg chart returns consistent labels/values."""
    chart = PokedexAPI.get_egg_chart(language_id=9, type_filter=None)
    assert chart.total > 0
    assert len(chart.labels) == len(chart.values)


def test_ability_charts_smoke_from_pikachu() -> None:
    """Ability charts work for a known ability."""
    pikachu = PokedexAPI.get_pokemon("pikachu", language_id=9)
    ability = pikachu["abilities"][0]

    chart_t = PokedexAPI.get_ability_type_chart(ability=ability, language_id=9)
    chart_g = PokedexAPI.get_ability_gen_chart(ability=ability, language_id=9)

    assert chart_t.total > 0
    assert len(chart_t.labels) == len(chart_t.values)

    assert chart_g.total > 0
    assert len(chart_g.labels) == len(chart_g.values)


def test_stat_histogram_smoke_pikachu_hp() -> None:
    """Stat histogram returns valid bins and metadata."""
    chart = PokedexAPI.get_stat_histogram(
        identifier="pikachu",
        stat_key="HP",
        language_id=9,
        bins=10,
        clamp_range=(0, 255),
    )
    assert isinstance(chart.labels, list)
    assert isinstance(chart.values, list)
    assert len(chart.labels) == len(chart.values)
    assert chart.total > 0
