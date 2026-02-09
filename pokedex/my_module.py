"""This module shows you how you can construct a nice documentation with
sphinx and the right syntaxe for docstrings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

pokemon_df = pd.read_csv("data/csv/pokemon.csv")
pokemon_evolution_df = pd.read_csv("data/csv/pokemon_evolution.csv")
pokemon_species_df = pd.read_csv("data/csv/pokemon_species.csv")


pokemon_types_df = pd.read_csv("data/csv/pokemon_types.csv")
types_df = pd.read_csv("data/csv/types.csv")
type_names_df = pd.read_csv("data/csv/type_names.csv")
# types_sprites_df= pd.read_csv("data/sprites/sprites/types/generation-ix/scarlet-violet.csv")

pokemon_stats_df = pd.read_csv("data/csv/pokemon_stats.csv")
stats_df = pd.read_csv("data/csv/stats.csv")

pokemon_forms_df = pd.read_csv("data/csv/pokemon_forms.csv")


pokemon_species_flavor_text_df = pd.read_csv("data/csv/pokemon_species_flavor_text.csv")
versions_df = pd.read_csv("data/csv/versions.csv")
languages_df = pd.read_csv("data/csv/languages.csv")
pokemon_species_names_df = pd.read_csv(
    "data/csv/pokemon_species_names.csv"
)  # for localized names

pokemon_egg_groups_df = pd.read_csv("data/csv/pokemon_egg_groups.csv")
egg_groups_prose_df = pd.read_csv("data/csv/egg_group_prose.csv")


pokemon_abilities_df = pd.read_csv("data/csv/pokemon_abilities.csv")
ability_names_df = pd.read_csv("data/csv/ability_names.csv")
ability_flavor_text_df = pd.read_csv("data/csv/ability_flavor_text.csv")

generation_names_df = pd.read_csv("data/csv/generation_names.csv")


items_df = pd.read_csv("data/csv/items.csv")
item_names_df = pd.read_csv("data/csv/item_names.csv")
item_flavor_text_df = pd.read_csv("data/csv/item_flavor_text.csv")


@dataclass(frozen=True)
class ChartData:
    title: str
    labels: list[str]
    values: list[int]
    total: int
    meta: dict[str, str]


@dataclass(frozen=True)
class PokemonEvolNode:
    dex_no: int
    name: str
    image: str
    evol_trigger_id: int
    evol_trigger_value: str = "NaN"
    evol_image: str = "NaN"
    evolutions: tuple[PokemonEvolNode, ...] = ()


class PokedexAPI:
    """
    pokemon_df = pd.read_csv("data/csv/pokemon.csv")
    pokemon_evolution_df = pd.read_csv("data/csv/pokemon_evolution.csv")
    pokemon_types_df = pd.read_csv("data/csv/pokemon_types.csv")
    types_df = pd.read_csv("data/csv/types.csv")

    dexNum = 25

    pokemonListSearch = pokemon_df[pokemon_df["species_id"] == dexNum]
    print(pokemonListSearch)
    """

    @staticmethod
    def get_pokemon(
        identifier: str | int, form: int | str | None = None, language_id: int = 9
    ) -> dict:
        # identifier can be DexNum (25) or name ("pikachu")

        if isinstance(identifier, str):
            try:
                dex = int(identifier)
                pokemon = pokemon_species_df[pokemon_species_df["id"] == dex]
            except ValueError:
                pokemon = pokemon_species_df[
                    pokemon_species_df["identifier"].str.lower() == identifier.lower()
                ]
        else:
            pokemon = pokemon_species_df[pokemon_species_df["id"] == identifier]
            dex = pokemon["id"].values[0] if not pokemon.empty else None

        if pokemon.empty:
            raise ValueError(f"Pokémon '{identifier}' not found")

        if form is not None:
            pokemon = pokemon_df[pokemon_df["identifier"].str.lower() == form]
            if pokemon.empty:
                raise ValueError(f"Pokémon '{identifier}' with form '{form}' not found")

        p = pokemon.iloc[0]
        p = pokemon_df[pokemon_df["id"] == p["id"]].iloc[0]
        pokemon_id = p["id"]
        pokemon_dexNum = p["species_id"]

        pokemon_types_list = pokemon_types_df[
            pokemon_types_df["pokemon_id"] == pokemon_id
        ]["type_id"].tolist()

        stats_list = pokemon_stats_df[pokemon_stats_df["pokemon_id"] == pokemon_id][
            ["stat_id", "base_stat"]
        ]

        # Evolution chain
        evolution_chain_id = pokemon_species_df[
            pokemon_species_df["id"] == pokemon_dexNum
        ]["evolution_chain_id"].values[0]
        evolution_chain = pokemon_species_df[
            pokemon_species_df["evolution_chain_id"] == evolution_chain_id
        ]

        start_row = (
            evolution_chain[evolution_chain["evolves_from_species_id"].isna()]
            .sort_values("id")
            .iloc[0]
        )

        evolution_tree = PokedexAPI.build_evolution_tree(
            species_id=int(start_row["id"]),
            language_id=language_id,
        )

        pokemon_forms_list = pokemon_df[pokemon_df["species_id"] == pokemon_dexNum][
            "identifier"
        ].tolist()

        pokemon_localized_name = pokemon_species_names_df[
            (pokemon_species_names_df["pokemon_species_id"] == pokemon_dexNum)
        ]
        pokemon_localized_name = pokemon_localized_name[
            pokemon_localized_name["local_language_id"] == language_id
        ]

        if not pokemon_localized_name.empty:
            pokemon_localized_name = pokemon_localized_name["name"].values[0]
        else:
            pokemon_localized_name = p["identifier"].capitalize()

        pokemon_egg_groups = pokemon_egg_groups_df[
            pokemon_egg_groups_df["species_id"] == pokemon_dexNum
        ]
        egg_group_ids = pokemon_egg_groups["egg_group_id"].tolist()

        egg_group_names = []
        for egg_group_id in egg_group_ids:
            egg_group_name = egg_groups_prose_df[
                (egg_groups_prose_df["egg_group_id"] == egg_group_id)
                & (egg_groups_prose_df["local_language_id"] == language_id)
            ]
            if not egg_group_name.empty:
                egg_group_names.append(egg_group_name["name"].values[0])

        pokemon_abilities = pokemon_abilities_df[
            pokemon_abilities_df["pokemon_id"] == pokemon_id
        ]
        ability_ids = pokemon_abilities["ability_id"].tolist()

        ability_names = []
        for ability_id in ability_ids:
            ability_name = ability_names_df[
                (ability_names_df["ability_id"] == ability_id)
                & (ability_names_df["local_language_id"] == language_id)
            ]
            if not ability_name.empty:
                ability_names.append(ability_name["name"].values[0])
            else:
                ability_name = ability_names_df[
                    (ability_names_df["ability_id"] == ability_id)
                    & (ability_names_df["local_language_id"] == 9)
                ]
                ability_names.append(ability_name["name"].values[0])

        is_hidden_ability_list = pokemon_abilities[
            pokemon_abilities["pokemon_id"] == pokemon_id
        ]["is_hidden"].tolist()

        return {
            "name": pokemon_localized_name,
            "dex_number": p["species_id"],
            # "image": f"data/sprites/sprites/pokemon/{int(p['id'])}.png",
            "image": f"data/sprites/sprites/pokemon/other/home/{int(p['id'])}.png",
            "cries": [f"data/cries/cries/pokemon/latest/{int(p['id'])}.ogg"],
            # "types": type_names.split(", "),
            "types": pokemon_types_list,
            "base_stats": {
                "HP": stats_list[stats_list["stat_id"] == 1]["base_stat"].values[0],
                "Atk": stats_list[stats_list["stat_id"] == 2]["base_stat"].values[0],
                "Def": stats_list[stats_list["stat_id"] == 3]["base_stat"].values[0],
                "SpA": stats_list[stats_list["stat_id"] == 4]["base_stat"].values[0],
                "SpD": stats_list[stats_list["stat_id"] == 5]["base_stat"].values[0],
                "Spe": stats_list[stats_list["stat_id"] == 6]["base_stat"].values[0],
            },
            "evolution_line": evolution_tree,
            "forms": pokemon_forms_list,
            "abilities": ability_names,
            "is_hidden_ability": is_hidden_ability_list,
            "egg_groups": egg_group_names,
        }

    @staticmethod
    def build_evolution_tree(
        species_id: int,
        language_id: int,
    ) -> PokemonEvolNode:
        # localized name
        name_row = pokemon_species_names_df[
            (pokemon_species_names_df["pokemon_species_id"] == species_id)
            & (pokemon_species_names_df["local_language_id"] == language_id)
        ]
        if not name_row.empty:
            name = str(name_row.iloc[0]["name"])
        else:
            sp = pokemon_species_df[pokemon_species_df["id"] == species_id].iloc[0]
            name = str(sp.get("identifier", str(species_id)))

        image = f"data/sprites/sprites/pokemon/{int(species_id)}.png"

        # --- evolution meta for THIS species (how you reach THIS node from its parent)
        evo_row = pokemon_evolution_df[
            pokemon_evolution_df["evolved_species_id"] == species_id
        ]
        if evo_row.empty:
            evol_trigger_id = 0
            evol_trigger_value = "NaN"
            evol_image = "NaN"
        else:
            r = evo_row.iloc[0]
            evol_trigger_id = (
                int(r["evolution_trigger_id"])
                if not PokedexAPI._is_nan(r["evolution_trigger_id"])
                else 0
            )

            parts: list[str] = []
            evol_image = "NaN"

            # Level
            if "minimum_level" in r and not PokedexAPI._is_nan(r["minimum_level"]):
                parts.append(f"Lv. {int(r['minimum_level'])}")

            # Happiness / Beauty / Affection
            if "minimum_happiness" in r and not PokedexAPI._is_nan(
                r["minimum_happiness"]
            ):
                parts.append(f"Happiness {int(r['minimum_happiness'])}")

            if "minimum_beauty" in r and not PokedexAPI._is_nan(r["minimum_beauty"]):
                parts.append(f"Beauty {int(r['minimum_beauty'])}")

            if "minimum_affection" in r and not PokedexAPI._is_nan(
                r["minimum_affection"]
            ):
                parts.append(f"Affection {int(r['minimum_affection'])}")

            # Time of day ("" means none)
            if (
                "time_of_day" in r
                and isinstance(r["time_of_day"], str)
                and r["time_of_day"].strip()
            ):
                parts.append(r["time_of_day"].strip())

            # Item used to trigger evolution
            trigger_item_id = None
            if "trigger_item_id" in r and not PokedexAPI._is_nan(r["trigger_item_id"]):
                trigger_item_id = int(r["trigger_item_id"])

            held_item_id = None
            if "held_item_id" in r and not PokedexAPI._is_nan(r["held_item_id"]):
                held_item_id = int(r["held_item_id"])

            if trigger_item_id is not None:
                item_name = PokedexAPI._get_item_localized_name(
                    trigger_item_id, language_id
                )
                if item_name is not None:
                    parts.append(item_name)

                item_identifier = PokedexAPI._get_item_identifier(trigger_item_id)
                if item_identifier is not None:
                    evol_image = f"data/sprites/sprites/items/{item_identifier}.png"

            elif held_item_id is not None:
                item_name = PokedexAPI._get_item_localized_name(
                    held_item_id, language_id
                )
                if item_name is not None:
                    parts.append(f"Held: {item_name}")

                item_identifier = PokedexAPI._get_item_identifier(held_item_id)
                if item_identifier is not None:
                    evol_image = f"data/sprites/sprites/items/{item_identifier}.png"

            # Known-move / location / other fields (only if they exist in your csv)
            if "known_move_id" in r and not PokedexAPI._is_nan(r["known_move_id"]):
                parts.append(f"Known move {int(r['known_move_id'])}")

            if "known_move_type_id" in r and not PokedexAPI._is_nan(
                r["known_move_type_id"]
            ):
                parts.append(f"Move type {int(r['known_move_type_id'])}")

            if "location_id" in r and not PokedexAPI._is_nan(r["location_id"]):
                parts.append(f"Location {int(r['location_id'])}")

            if "gender_id" in r and not PokedexAPI._is_nan(r["gender_id"]):
                parts.append(f"Gender {int(r['gender_id'])}")

            if "min_level" in r and not PokedexAPI._is_nan(r["min_level"]):
                # just in case your csv uses a different column name
                parts.append(f"Lv. {int(r['min_level'])}")

            # Boolean-ish flags if present
            if (
                "needs_overworld_rain" in r
                and not PokedexAPI._is_nan(r["needs_overworld_rain"])
                and bool(r["needs_overworld_rain"])
            ):
                parts.append("Rain")

            if (
                "turn_upside_down" in r
                and not PokedexAPI._is_nan(r["turn_upside_down"])
                and bool(r["turn_upside_down"])
            ):
                parts.append("Upside down")

            evol_trigger_value = ", ".join(parts) if parts else "NaN"

        # children species
        children = (
            pokemon_species_df[
                pokemon_species_df["evolves_from_species_id"] == species_id
            ]
            .sort_values("id")["id"]
            .tolist()
        )

        child_nodes = tuple(
            PokedexAPI.build_evolution_tree(
                species_id=int(child_id),
                language_id=language_id,
            )
            for child_id in children
        )

        return PokemonEvolNode(
            dex_no=int(species_id),
            name=name,
            image=image,
            evol_trigger_id=evol_trigger_id,
            evol_trigger_value=evol_trigger_value,
            evol_image=evol_image,
            evolutions=child_nodes,
        )

    @staticmethod
    def get_available_forms(identifier: str | int) -> list[str]:
        if isinstance(identifier, str):
            try:
                dex = int(identifier)
                pokemon = pokemon_species_df[pokemon_species_df["id"] == dex]
            except ValueError:
                pokemon = pokemon_species_df[
                    pokemon_species_df["identifier"].str.lower() == identifier.lower()
                ]
        else:
            pokemon = pokemon_species_df[pokemon_species_df["id"] == identifier]
            dex = pokemon["id"].values[0] if not pokemon.empty else None

        if pokemon.empty:
            raise ValueError(f"Pokémon '{identifier}' not found")

        p = pokemon.iloc[0]
        p = pokemon_df[pokemon_df["id"] == p["id"]].iloc[0]

        pokemon_dexNum = p["species_id"]
        pokemon_forms_list = pokemon_df[pokemon_df["species_id"] == pokemon_dexNum][
            "identifier"
        ].tolist()
        return pokemon_forms_list

    @staticmethod
    def get_pokedex_flavor(identifier: str | int, language_id: int = 9) -> dict:
        if isinstance(identifier, str):
            try:
                id = int(identifier)
                pokemon = pokemon_df[pokemon_df["id"] == id]
            except ValueError:
                pokemon = pokemon_df[
                    pokemon_df["identifier"].str.lower() == identifier.lower()
                ]
        else:
            pokemon = pokemon_df[pokemon_df["id"] == identifier]

        if pokemon.empty:
            raise ValueError(f"Pokémon '{identifier}' not found")

        p = pokemon.iloc[0]
        p = pokemon_df[pokemon_df["id"] == p["id"]].iloc[0]
        pokemon_dexNum = p["species_id"]

        flavor_dataframe = pokemon_species_flavor_text_df[
            pokemon_species_flavor_text_df["language_id"] == language_id
        ]
        flavor_dataframe = flavor_dataframe[
            flavor_dataframe["species_id"] == pokemon_dexNum
        ]

        versions_list = versions_df[
            versions_df["id"].isin(flavor_dataframe["version_id"].values.tolist())
        ]["identifier"].tolist()
        flavor_texts_list = flavor_dataframe["flavor_text"].values.tolist()

        return {"versions": versions_list, "flavor_texts": flavor_texts_list}

    @staticmethod
    def get_ability_description(
        ability: str, is_hidden: bool, language_id: int = 9
    ) -> str:
        ability_str = str(ability).strip()
        if not ability_str:
            raise ValueError("Ability is empty")

        # 1) Find ability_id by ability name (case-insensitive)

        row = ability_names_df[
            ability_names_df["name"].astype(str).str.casefold()
            == ability_str.casefold()
        ]

        # Optional fallback: if you store identifiers too
        if row.empty and "identifier" in ability_names_df.columns:
            row = ability_names_df[
                ability_names_df["identifier"].astype(str).str.casefold()
                == ability_str.casefold()
            ]

        if row.empty:
            raise ValueError(f"Ability '{ability_str}' not found in ability_names_df")

        ability_id = int(row["ability_id"].iloc[0])

        # 2) Get flavor text in requested language, fallback to English (9)
        flavor = ability_flavor_text_df[
            (ability_flavor_text_df["ability_id"] == ability_id)
            & (ability_flavor_text_df["language_id"] == language_id)
        ]

        if flavor.empty:
            flavor = ability_flavor_text_df[
                (ability_flavor_text_df["ability_id"] == ability_id)
                & (ability_flavor_text_df["language_id"] == 9)
            ]

        if flavor.empty or "flavor_text" not in flavor.columns:
            raise ValueError(
                f"Ability '{ability_str}' description not found for language ID '{language_id}'"
            )

        # Last available flavor text (latest game version)
        text = str(flavor["flavor_text"].iloc[-1])
        text = text.replace("\n", " ").replace("\f", " ").strip()

        if bool(is_hidden):
            text = f"(Hidden Ability) {text}"

        return text

    @staticmethod
    def get_type_chart(language_id: int = 9,
        forms_enable: bool = False,
        generations_enable: list[bool] | None = None,
    ) -> ChartData:
        if generations_enable is None:
            generations_enable = [True] * 9

        if not forms_enable:
            pokemon_types_df_filtered = pokemon_types_df[
                pokemon_types_df["pokemon_id"] <= 10000
            ]
        else:
            pokemon_types_df_filtered = pokemon_types_df

        for gen_index, gen_enabled in enumerate(generations_enable):
            if not gen_enabled:
                pokemon_species_df_filtered = pokemon_species_df[
                    pokemon_species_df["generation_id"] == (gen_index + 1)
                ]

                pokemon_ids_to_exclude = pokemon_species_df_filtered["id"].tolist()

                pokemon_df_filtered = pokemon_df[
                    pokemon_df["species_id"].isin(pokemon_ids_to_exclude)
                ]

                pokemon_types_df_filtered = pokemon_types_df_filtered[
                    ~pokemon_types_df_filtered["pokemon_id"].isin(
                        pokemon_df_filtered["id"]
                    )
                ]

        count_by_type = pokemon_types_df_filtered["type_id"].value_counts().to_dict()

        labels = list(count_by_type.keys())
        out: list[str] = []
        for label in labels:
            s = type_names_df[
                (type_names_df["type_id"] == label)
                & (type_names_df["local_language_id"] == language_id)
            ]["name"]

            if s.empty:
                s = type_names_df[
                    (type_names_df["type_id"] == label)
                    & (type_names_df["local_language_id"] == 9)
                ]["name"]

            out.append(str(s.iloc[0]))
        labels = out

        values = list(count_by_type.values())
        total = pokemon_types_df_filtered["pokemon_id"].nunique()

        return ChartData(
            title="Type Chart",
            labels=labels,
            values=values,
            total=total,
            meta={"description": "Type chart for all types"},
        )

    @staticmethod
    def get_gen_chart(language_id: int = 9,
        type_filter: str | None = None,
    ) -> ChartData:
        if type_filter is None:
            type_id_filter = None
        else:
            type_row = types_df[
                types_df["identifier"].str.lower() == type_filter.lower()
            ]
            if type_row.empty:
                raise ValueError(f"Type '{type_filter}' not found")
            type_id_filter = int(type_row["id"].iloc[0])

        pokemon_types_df_filtered = pokemon_types_df[
            pokemon_types_df["pokemon_id"] <= 10000
        ]

        pokemon_filtered = pokemon_types_df_filtered["pokemon_id"].tolist()
        if type_id_filter is not None:
            pokemon_filtered = pokemon_types_df_filtered[
                pokemon_types_df_filtered["type_id"] == type_id_filter
            ]["pokemon_id"].tolist()

        pokemon_df_filtered = pokemon_df[pokemon_df["id"].isin(pokemon_filtered)]
        pokemon_species_df_filtered = pokemon_species_df[
            pokemon_species_df["id"].isin(pokemon_filtered)
        ]

        count_by_gen = (
            pokemon_species_df_filtered["generation_id"].value_counts().to_dict()
        )

        labels = list(count_by_gen.keys())
        out: list[str] = []
        for label in labels:
            s = generation_names_df[
                (generation_names_df["generation_id"] == label)
                & (generation_names_df["local_language_id"] == language_id)
            ]["name"]

            if s.empty:
                s = generation_names_df[
                    (generation_names_df["generation_id"] == label)
                    & (generation_names_df["local_language_id"] == 9)
                ]["name"]

            out.append(str(s.iloc[0]))
        labels = out

        values = list(count_by_gen.values())
        total = pokemon_df_filtered["species_id"].nunique()

        return ChartData(
            title="Generation Chart",
            labels=labels,
            values=values,
            total=total,
            meta={"description": "Generation chart for all generations"},
        )

    @staticmethod
    def get_all_types(language_id: int = 9) -> list[tuple[str, str]] | list[str]:
        types_df_filtered = types_df[types_df["id"] <= 18]["id"].tolist()

        type_names_list = type_names_df[
            (type_names_df["local_language_id"] == language_id)
            & (type_names_df["type_id"].isin(types_df_filtered))
        ]["name"].tolist()

        return type_names_list

    @staticmethod
    def get_all_abilities(language_id: int = 9) -> list[str] | list[tuple[str, str]]:
        ability_names_df_filtered = ability_names_df[
            ability_names_df["local_language_id"] == language_id
        ]["name"].tolist()
        return ability_names_df_filtered

    @staticmethod
    def get_all_egg_groups(language_id: int = 9) -> list[str] | list[tuple[str, str]]:
        egg_groups_prose_df_filtered = egg_groups_prose_df[
            egg_groups_prose_df["local_language_id"] == language_id
        ]["name"].tolist()
        return egg_groups_prose_df_filtered

    @staticmethod
    def get_all_items(language_id: int = 9) -> list[str] | list[tuple[str, str]]:
        all_item_ids = item_flavor_text_df["item_id"].unique().tolist()

        item_names_df_filtered = item_names_df[
            item_names_df["local_language_id"] == language_id
        ]

        item_names_filtered = item_names_df_filtered[
            item_names_df_filtered["item_id"].isin(all_item_ids)
        ]["name"].tolist()

        return item_names_filtered

    @staticmethod
    def get_egg_chart( language_id: int = 9,
        type_filter: str | None = None,
        generations_enable: list[bool] | None = None,
    ) -> ChartData:
        if generations_enable is None:
            generations_enable = [True] * 9

        egg_df = pokemon_egg_groups_df.copy()

        # 1) Generation filtering (exclude disabled gens) using species_id directly
        disabled_gens = [
            i + 1 for i, enabled in enumerate(generations_enable) if not enabled
        ]
        if disabled_gens:
            species_to_exclude = pokemon_species_df[
                pokemon_species_df["generation_id"].isin(disabled_gens)
            ]["id"].unique()
            egg_df = egg_df[~egg_df["species_id"].isin(species_to_exclude)]

        # 2) Type filter (keep only species that have the given type)
        if type_filter is not None:
            type_row = types_df[
                types_df["identifier"].astype(str).str.lower()
                == str(type_filter).lower()
            ]
            if type_row.empty:
                raise ValueError(f"Type '{type_filter}' not found")
            type_id = int(type_row["id"].iloc[0])

            pokemon_ids_with_type = pokemon_types_df[
                pokemon_types_df["type_id"] == type_id
            ]["pokemon_id"].unique()

            species_ids_with_type = pokemon_df[
                pokemon_df["id"].isin(pokemon_ids_with_type)
            ]["species_id"].unique()

            egg_df = egg_df[egg_df["species_id"].isin(species_ids_with_type)]

        # 3) Count
        counts = egg_df["egg_group_id"].value_counts()
        values = counts.values.tolist()
        egg_group_ids = counts.index.tolist()

        # 4) Labels (always append, with fallback)
        labels: list[str] = []
        for egg_id in egg_group_ids:
            s = egg_groups_prose_df[
                (egg_groups_prose_df["egg_group_id"] == egg_id)
                & (egg_groups_prose_df["local_language_id"] == language_id)
            ]["name"]

            if s.empty:
                s = egg_groups_prose_df[
                    (egg_groups_prose_df["egg_group_id"] == egg_id)
                    & (egg_groups_prose_df["local_language_id"] == 9)
                ]["name"]

            labels.append(str(s.iloc[0]) if not s.empty else str(egg_id))

        total = int(egg_df["species_id"].nunique())

        return ChartData(
            title="Egg Group Chart",
            labels=labels,
            values=values,
            total=total,
            meta={"description": "Egg group chart for all egg groups"},
        )

    @staticmethod
    def get_ability_type_chart( ability: str,
        language_id: int = 9,
    ) -> ChartData:
        ability_str = str(ability).strip()
        if not ability_str:
            raise ValueError("Ability is empty")

        # 1) Find ability_id by ability name (case-insensitive)

        row = ability_names_df[
            ability_names_df["name"].astype(str).str.casefold()
            == ability_str.casefold()
        ]

        # Optional fallback: if you store identifiers too
        if row.empty and "identifier" in ability_names_df.columns:
            row = ability_names_df[
                ability_names_df["identifier"].astype(str).str.casefold()
                == ability_str.casefold()
            ]

        if row.empty:
            raise ValueError(f"Ability '{ability_str}' not found in ability_names_df")

        ability_id = int(row["ability_id"].iloc[0])

        pokemon_filtered = pokemon_abilities_df[
            pokemon_abilities_df["ability_id"] == ability_id
        ]["pokemon_id"].tolist()

        pokemon_types_df_filtered = pokemon_types_df[
            pokemon_types_df["pokemon_id"].isin(pokemon_filtered)
        ]

        count_by_type = pokemon_types_df_filtered["type_id"].value_counts().to_dict()

        labels = list(count_by_type.keys())
        out: list[str] = []
        for label in labels:
            s = type_names_df[
                (type_names_df["type_id"] == label)
                & (type_names_df["local_language_id"] == language_id)
            ]["name"]

            if s.empty:
                s = type_names_df[
                    (type_names_df["type_id"] == label)
                    & (type_names_df["local_language_id"] == 9)
                ]["name"]

            out.append(str(s.iloc[0]))
        labels = out

        values = list(count_by_type.values())
        total = pokemon_types_df_filtered["pokemon_id"].nunique()

        return ChartData(
            title="Type Chart - Ability: " + ability_str,
            labels=labels,
            values=values,
            total=total,
            meta={"description": "Type chart for selected ability"},
        )

    @staticmethod
    def get_ability_gen_chart( ability: str,
        language_id: int = 9,
    ) -> ChartData:
        ability_str = str(ability).strip()
        if not ability_str:
            raise ValueError("Ability is empty")

        # 1) Find ability_id by ability name (case-insensitive)

        row = ability_names_df[
            ability_names_df["name"].astype(str).str.casefold()
            == ability_str.casefold()
        ]

        # Optional fallback: if you store identifiers too
        if row.empty and "identifier" in ability_names_df.columns:
            row = ability_names_df[
                ability_names_df["identifier"].astype(str).str.casefold()
                == ability_str.casefold()
            ]

        if row.empty:
            raise ValueError(f"Ability '{ability_str}' not found in ability_names_df")

        ability_id = int(row["ability_id"].iloc[0])

        pokemon_filtered = pokemon_abilities_df[
            pokemon_abilities_df["ability_id"] == ability_id
        ]["pokemon_id"].tolist()

        pokemon_df_filtered = pokemon_df[pokemon_df["id"].isin(pokemon_filtered)]
        pokemon_species_df_filtered = pokemon_species_df[
            pokemon_species_df["id"].isin(pokemon_filtered)
        ]

        count_by_gen = (
            pokemon_species_df_filtered["generation_id"].value_counts().to_dict()
        )

        labels = list(count_by_gen.keys())
        out: list[str] = []
        for label in labels:
            s = generation_names_df[
                (generation_names_df["generation_id"] == label)
                & (generation_names_df["local_language_id"] == language_id)
            ]["name"]

            if s.empty:
                s = generation_names_df[
                    (generation_names_df["generation_id"] == label)
                    & (generation_names_df["local_language_id"] == 9)
                ]["name"]

            out.append(str(s.iloc[0]))
        labels = out

        values = list(count_by_gen.values())
        total = pokemon_df_filtered["species_id"].nunique()

        return ChartData(
            title="Generation Chart - Ability: " + ability_str,
            labels=labels,
            values=values,
            total=total,
            meta={"description": "Generation chart for selected ability"},
        )

    @staticmethod
    def get_item(item: str, language_id: int = 9) -> dict:
        item_str = str(item).strip()

        if not item_str:
            raise ValueError("Item is empty")

        # 1) Find item_id by item name (case-insensitive)

        row = item_names_df[
            item_names_df["name"].astype(str).str.casefold() == item_str.casefold()
        ]

        # Optional fallback: if you store item_id too
        if row.empty:
            row = item_names_df[
                item_names_df["item_id"].astype(str).str.casefold()
                == item_str.casefold()
            ]

        if row.empty:
            raise ValueError(f"Item '{item_str}' not found in item_names_df")
        item_id = int(row["item_id"].iloc[0])

        # 2) Get flavor text in requested language, fallback to English (9)
        flavor = item_flavor_text_df[
            (item_flavor_text_df["item_id"] == item_id)
            & (item_flavor_text_df["language_id"] == language_id)
        ]

        if flavor.empty:
            flavor = item_flavor_text_df[
                (item_flavor_text_df["item_id"] == item_id)
                & (item_flavor_text_df["language_id"] == 9)
            ]

        if flavor.empty or "flavor_text" not in flavor.columns:
            raise ValueError(
                f"Item '{item_str}' description not found for language ID '{language_id}'"
            )

        item_name = item_names_df[(item_names_df["item_id"] == item_id)]

        item_name = item_name[item_name["local_language_id"] == language_id]["name"]

        if item_name.empty:
            item_name = item_names_df[
                (item_names_df["item_id"] == item_id)
                & (item_names_df["local_language_id"] == 9)
            ]["name"]

        identifier = items_df[items_df["id"] == item_id]["identifier"]
        if identifier.empty:
            raise ValueError(f"Item identifier not found for item ID '{item_id}'")
        identifier = identifier.iloc[0]

        # Last available flavor text (latest game version)

        text = str(flavor["flavor_text"].iloc[-1])
        text = text.replace("\n", " ").replace("\f", " ").strip()

        return {
            "name": item_name.iloc[0] if not item_name.empty else "Unknown",
            "item_flavor_text": text,
            "image": f"data/sprites/sprites/items/{str(identifier)}.png",
        }

    @staticmethod
    def get_stat_histogram(
        identifier: str | int,
        stat_key: str,  # "HP","Atk","Def","SpA","SpD","Spe" (also accepts "hp", "attack", etc.)
        language_id: int = 9,
        type_filter: str | None = None,  # types_df.identifier (e.g. "electric")
        forms_enable: bool = False,
        generations_enable: list[bool] | None = None,
        bins: int = 20,
        clamp_range: tuple[int, int]
        | None = None,  # e.g. (0, 255) if you want fixed range
        form: int | str | None = None,  # optional, same idea as get_pokemon
    ) -> ChartData:
        """
        Build a histogram of a given base stat over the pokemons selected by filters,
        and include metadata to highlight the selected pokemon.

        Also includes ranking info for the selected pokemon within the filtered set:
        - selected_rank: 1 means best/highest value
        - rank_total: number of pokemons considered
        - selected_value: absolute stat value

        Returns:
            ChartData: labels are bin ranges, values are counts, meta includes selected marker + rank info.
        """

        if generations_enable is None:
            generations_enable = [True] * 9

        stat_key_clean = str(stat_key).strip()

        alias_map = {
            "HP": "hp",
            "Atk": "attack",
            "Def": "defense",
            "SpA": "special-attack",
            "SpD": "special-defense",
            "Spe": "speed",
        }

        if stat_key_clean in alias_map:
            stat_identifier = alias_map[stat_key_clean]
        else:
            stat_identifier = stat_key_clean.lower().replace(" ", "-")

        stat_row = stats_df[
            stats_df["identifier"].astype(str).str.casefold()
            == stat_identifier.casefold()
        ]
        if stat_row.empty:
            try:
                stat_id = int(stat_key_clean)
            except ValueError as e:
                raise ValueError(
                    f"Unknown stat_key '{stat_key}'. Expected one of {list(alias_map.keys())} or a stats_df identifier."
                ) from e
        else:
            stat_id = int(stat_row["id"].iloc[0])

        if not forms_enable:
            pokemon_df_filtered = pokemon_df[pokemon_df["id"] <= 10000].copy()
        else:
            pokemon_df_filtered = pokemon_df.copy()

        disabled_gens = [
            i + 1 for i, enabled in enumerate(generations_enable) if not enabled
        ]
        if disabled_gens:
            species_to_exclude = pokemon_species_df[
                pokemon_species_df["generation_id"].isin(disabled_gens)
            ]["id"].unique()

            pokemon_df_filtered = pokemon_df_filtered[
                ~pokemon_df_filtered["species_id"].isin(species_to_exclude)
            ]

        type_id_filter: int | None = None
        if type_filter is not None:
            type_row = types_df[
                types_df["identifier"].astype(str).str.casefold()
                == str(type_filter).casefold()
            ]
            if type_row.empty:
                raise ValueError(f"Type '{type_filter}' not found")
            type_id_filter = int(type_row["id"].iloc[0])

            pokemon_ids_with_type = pokemon_types_df[
                pokemon_types_df["type_id"] == type_id_filter
            ]["pokemon_id"].unique()

            pokemon_df_filtered = pokemon_df_filtered[
                pokemon_df_filtered["id"].isin(pokemon_ids_with_type)
            ]

        pokemon_ids = pokemon_df_filtered["id"].unique()

        stat_values_df = pokemon_stats_df[
            (pokemon_stats_df["pokemon_id"].isin(pokemon_ids))
            & (pokemon_stats_df["stat_id"] == stat_id)
        ][["pokemon_id", "base_stat"]].copy()

        if stat_values_df.empty:
            return ChartData(
                title=f"Histogram - {stat_key_clean}",
                labels=[],
                values=[],
                total=0,
                meta={
                    "description": "No data for selected filters",
                    "stat_key": stat_key_clean,
                    "stat_id": str(stat_id),
                    "selected_identifier": str(identifier),
                    "selected_pokemon_id": "None",
                    "selected_value": "None",
                    "selected_bin_index": "None",
                    "selected_rank": "None",
                    "rank_total": "0",
                    "tied_with": "None",
                    "type_filter": str(type_filter)
                    if type_filter is not None
                    else "None",
                    "forms_enable": str(bool(forms_enable)),
                    "generations_enable": ",".join(
                        ["1" if x else "0" for x in generations_enable]
                    ),
                    "language_id": str(language_id),
                },
            )

        values = stat_values_df["base_stat"].astype(int).to_numpy()

        vmin = int(values.min())
        vmax = int(values.max())

        if clamp_range is not None:
            cmin, cmax = clamp_range
            vmin = min(vmin, int(cmin))
            vmax = max(vmax, int(cmax))

        if vmin == vmax:
            edges = np.array([vmin - 1, vmax + 1], dtype=float)
        else:
            edges = np.linspace(vmin, vmax, int(bins) + 1, dtype=float)

        counts, bin_edges = np.histogram(values, bins=edges)

        labels: list[str] = []
        for i in range(len(bin_edges) - 1):
            left = int(round(bin_edges[i]))
            right = int(round(bin_edges[i + 1]))
            if i < len(bin_edges) - 2:
                labels.append(f"{left}–{right - 1}")
            else:
                labels.append(f"{left}–{right}")

        # Resolve selected pokemon_id (species identifier or name; optional explicit form)
        selected_pokemon_id: int | None = None
        if isinstance(identifier, str):
            try:
                dex = int(identifier)
                species_row = pokemon_species_df[pokemon_species_df["id"] == dex]
            except ValueError:
                species_row = pokemon_species_df[
                    pokemon_species_df["identifier"].astype(str).str.casefold()
                    == identifier.casefold()
                ]
        else:
            species_row = pokemon_species_df[pokemon_species_df["id"] == identifier]

        if not species_row.empty:
            dex_num = int(species_row["id"].iloc[0])

            if form is not None:
                form_row = pokemon_df[
                    pokemon_df["identifier"].astype(str).str.casefold()
                    == str(form).casefold()
                ]
                if not form_row.empty:
                    selected_pokemon_id = int(form_row["id"].iloc[0])
            else:
                base_row = pokemon_df[pokemon_df["species_id"] == dex_num].sort_values(
                    "id"
                )
                if not base_row.empty:
                    selected_pokemon_id = int(base_row["id"].iloc[0])

        selected_value: int | None = None
        selected_bin_index: int | None = None
        selected_rank: int | None = None
        tied_with: int | None = None

        total = int(stat_values_df["pokemon_id"].nunique())

        selected_in_filtered = (
            selected_pokemon_id is not None
            and selected_pokemon_id
            in set(stat_values_df["pokemon_id"].astype(int).tolist())
        )

        if selected_pokemon_id is not None:
            sel_row = pokemon_stats_df[
                (pokemon_stats_df["pokemon_id"] == selected_pokemon_id)
                & (pokemon_stats_df["stat_id"] == stat_id)
            ]
            if not sel_row.empty:
                selected_value = int(sel_row["base_stat"].iloc[0])

                # bin index only makes sense if the selected pokemon is in the filtered distribution
                if selected_in_filtered and len(bin_edges) >= 2:
                    if selected_value == int(round(bin_edges[-1])):
                        selected_bin_index = len(counts) - 1
                    else:
                        idx = int(
                            np.searchsorted(bin_edges, selected_value, side="right") - 1
                        )
                        if 0 <= idx < len(counts):
                            selected_bin_index = idx

                # Ranking only within filtered set
                if selected_in_filtered:
                    base_stats_series = stat_values_df["base_stat"].astype(int)
                    higher_count = int((base_stats_series > selected_value).sum())
                    selected_rank = higher_count + 1
                    tied_with = int((base_stats_series == selected_value).sum())

        return ChartData(
            title=f"Histogram - {stat_key_clean}",
            labels=labels,
            values=counts.astype(int).tolist(),
            total=total,
            meta={
                "description": "Base stat histogram with selected marker + rank",
                "stat_key": stat_key_clean,
                "stat_id": str(stat_id),
                "bins": str(len(counts)),
                "bin_edges": ",".join([str(float(x)) for x in bin_edges.tolist()]),
                "selected_identifier": str(identifier),
                "selected_pokemon_id": str(selected_pokemon_id)
                if selected_pokemon_id is not None
                else "None",
                "selected_value": str(selected_value)
                if selected_value is not None
                else "None",
                "selected_bin_index": str(selected_bin_index)
                if selected_bin_index is not None
                else "None",
                "selected_rank": str(selected_rank)
                if selected_rank is not None
                else "None",
                "rank_total": str(total),
                "tied_with": str(tied_with) if tied_with is not None else "None",
                "type_filter": str(type_filter) if type_filter is not None else "None",
                "forms_enable": str(bool(forms_enable)),
                "generations_enable": ",".join(
                    ["1" if x else "0" for x in generations_enable]
                ),
                "language_id": str(language_id),
            },
        )

    @staticmethod
    def _is_nan(x) -> bool:
        return x is None or (isinstance(x, float) and math.isnan(x))

    @staticmethod
    def _get_item_identifier(item_id: int) -> str | None:
        row = items_df[items_df["id"] == item_id]["identifier"]
        if row.empty:
            return None
        return str(row.iloc[0])

    @staticmethod
    def _get_item_localized_name(item_id: int, language_id: int) -> str | None:
        """
        PokedexAPI.Get item localized name.

        Return a localized item name for an item id, with English fallback.

        Reads from: ``item_names_df``.

        Parameters
        ----------
        item_id: Any
            Input parameter used to filter or select records.
        language_id: Any
            Input parameter used to filter or select records.
        """
        s = item_names_df[
            (item_names_df["item_id"] == item_id)
            & (item_names_df["local_language_id"] == language_id)
        ]["name"]
        if s.empty:
            s = item_names_df[
                (item_names_df["item_id"] == item_id)
                & (item_names_df["local_language_id"] == 9)
            ]["name"]
        if s.empty:
            return None
        return str(s.iloc[0])
