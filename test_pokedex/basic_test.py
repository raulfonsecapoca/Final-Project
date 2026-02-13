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

    Validation by dex numbers to avoid language-dependent name comparisons.
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
    """Type chart works with forms and gen filters."""
    chart = PokedexAPI.get_type_chart(
        language_id=5,  # non-English to hit fallback paths
        forms_enable=True,
        generations_enable=[True, False, True, True, True, True, True, True, True],
    )
    assert chart.total > 0
    assert len(chart.labels) == len(chart.values)
    assert all(isinstance(x, str) and x.strip() for x in chart.labels)
    assert all(isinstance(v, int) and v >= 0 for v in chart.values)


def test_gen_chart_smoke() -> None:
    """Gen chart works with a type filter."""
    chart = PokedexAPI.get_gen_chart(language_id=9, type_filter="electric")
    assert chart.total > 0
    assert len(chart.labels) == len(chart.values)
    assert all(isinstance(x, str) and x.strip() for x in chart.labels)
    assert all(isinstance(v, int) and v >= 0 for v in chart.values)


def test_egg_chart_smoke() -> None:
    """Egg chart works with type + gen filters."""
    chart = PokedexAPI.get_egg_chart(
        language_id=6,  # non-English to hit fallback paths
        type_filter="electric",
        generations_enable=[True, True, True, False, True, True, True, True, True],
    )
    assert chart.total > 0
    assert len(chart.labels) == len(chart.values)
    assert all(isinstance(x, str) and x.strip() for x in chart.labels)
    assert all(isinstance(v, int) and v >= 0 for v in chart.values)


def test_ability_charts_smoke_from_pikachu() -> None:
    """Ability charts cover non-English and multiple branches."""
    pikachu = PokedexAPI.get_pokemon("pikachu", language_id=9)
    ability = pikachu["abilities"][0]

    chart_t = PokedexAPI.get_ability_type_chart(ability=ability, language_id=5)
    chart_g = PokedexAPI.get_ability_gen_chart(ability=ability, language_id=6)

    assert chart_t.total > 0
    assert len(chart_t.labels) == len(chart_t.values)

    assert chart_g.total > 0
    assert len(chart_g.labels) == len(chart_g.values)


def test_stat_histogram_smoke_pikachu_hp() -> None:
    """Histogram covers filters, forms and edge paths."""
    chart = PokedexAPI.get_stat_histogram(
        identifier="pikachu",
        stat_key="hp",  # exercise alias path vs "HP"
        language_id=5,  # non-English to hit fallback
        type_filter="electric",
        forms_enable=True,
        generations_enable=[True, True, True, True, False, True, True, True, True],
        bins=12,
        clamp_range=(0, 255),
    )
    assert isinstance(chart.labels, list)
    assert isinstance(chart.values, list)
    assert len(chart.labels) == len(chart.values)
    assert chart.total > 0
    assert "selected_identifier" in chart.meta
    assert "selected_value" in chart.meta


def test_get_pokemon_invalid_identifier_raises() -> None:
    """Invalid Pokémon should raise ValueError."""
    with pytest.raises(ValueError):
        PokedexAPI.get_pokemon("not_a_real_pokemon")


def test_get_ability_description_hidden_flag() -> None:
    """Ability description handles hidden flag."""
    pikachu = PokedexAPI.get_pokemon("pikachu", language_id=9)
    ability = pikachu["abilities"][0]
    desc = PokedexAPI.get_ability_description(
        ability=ability,
        is_hidden=True,
        language_id=5,  # non-English
    )
    assert isinstance(desc, str)
    assert desc.startswith("(Hidden Ability)")


def test_type_name_non_english_language() -> None:
    """Non-English language returns non-empty type list."""
    types = PokedexAPI.get_all_types(language_id=5)
    assert isinstance(types, list)
    assert len(types) > 0


def test_stat_histogram_no_data_branch() -> None:
    """Histogram handles empty filtered result."""
    chart = PokedexAPI.get_stat_histogram(
        identifier="pikachu",
        stat_key="HP",
        language_id=9,
        type_filter="ghost",  # unlikely combo for Pikachu
        generations_enable=[False] * 9,  # disable everything
    )
    assert chart.total == 0
    assert chart.labels == []
    assert chart.values == []


def test_get_gen_chart_with_localized_type() -> None:
    """Gen chart resolves localized type names."""
    chart = PokedexAPI.get_gen_chart(language_id=5, type_filter="Électrik")
    assert chart.total > 0


def test_get_pokemon_with_valid_form_and_invalid_form() -> None:
    """Covers form branch and invalid form error."""
    forms = PokedexAPI.get_available_forms("pikachu")
    assert isinstance(forms, list)
    assert len(forms) > 0

    payload = PokedexAPI.get_pokemon("pikachu", form=forms[0])
    assert payload["forms"]

    with pytest.raises(ValueError):
        PokedexAPI.get_pokemon("pikachu", form="not_a_real_form")


def test_get_available_forms_invalid_identifier() -> None:
    """Invalid identifier raises in get_available_forms."""
    with pytest.raises(ValueError):
        PokedexAPI.get_available_forms("not_a_real_pokemon")


def test_get_item_error_paths() -> None:
    """Covers item empty and invalid error branches."""
    with pytest.raises(ValueError):
        PokedexAPI.get_item("")

    with pytest.raises(ValueError):
        PokedexAPI.get_item("not_a_real_item")


def test_get_ability_error_paths() -> None:
    """Covers ability empty and invalid branches."""
    with pytest.raises(ValueError):
        PokedexAPI.get_ability_description("", False)

    with pytest.raises(ValueError):
        PokedexAPI.get_ability_description("not_a_real_ability", False)


def test_stat_histogram_invalid_stat_key() -> None:
    """Invalid stat key raises ValueError."""
    with pytest.raises(ValueError):
        PokedexAPI.get_stat_histogram(
            identifier="pikachu",
            stat_key="not_a_stat",
        )


def test_type_filter_invalid_raises() -> None:
    """Invalid type filter raises error."""
    with pytest.raises(ValueError):
        PokedexAPI.get_gen_chart(language_id=9, type_filter="not_a_type")
