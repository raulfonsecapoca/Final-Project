"""This module shows you how you can construct a nice documentation with
sphinx and the right syntaxe for docstrings.
"""

import numpy as np
import pandas as pd

pokemon_df = pd.read_csv("data/csv/pokemon.csv")
pokemon_evolution_df = pd.read_csv("data/csv/pokemon_evolution.csv")
pokemon_species_df = pd.read_csv("data/csv/pokemon_species.csv")

pokemon_types_df = pd.read_csv("data/csv/pokemon_types.csv")
types_df = pd.read_csv("data/csv/types.csv")

pokemon_stats_df = pd.read_csv("data/csv/pokemon_stats.csv")
stats_df = pd.read_csv("data/csv/stats.csv")

pokemon_forms_df = pd.read_csv("data/csv/pokemon_forms.csv")


pokemon_species_flavor_text_df = pd.read_csv("data/csv/pokemon_species_flavor_text.csv")
versions_df = pd.read_csv("data/csv/versions.csv")
languages_df = pd.read_csv("data/csv/languages.csv")
pokemon_species_names_df = pd.read_csv("data/csv/pokemon_species_names.csv") # for localized names

class typed_function:

    '''
    pokemon_df = pd.read_csv("data/csv/pokemon.csv")
    pokemon_evolution_df = pd.read_csv("data/csv/pokemon_evolution.csv")
    pokemon_types_df = pd.read_csv("data/csv/pokemon_types.csv")
    types_df = pd.read_csv("data/csv/types.csv")

    dexNum = 25

    pokemonListSearch = pokemon_df[pokemon_df["species_id"] == dexNum]
    print(pokemonListSearch)
    '''


    @staticmethod
    def get_pokemon(identifier, form=None, language_id=9):
        # identifier can be DexNum (25) or name ("pikachu")

        if isinstance(identifier, str):
            try:
                dex = int(identifier)
                pokemon = pokemon_species_df[pokemon_species_df["id"] == dex]
            except ValueError:
                pokemon = pokemon_species_df[pokemon_species_df["identifier"].str.lower() == identifier.lower()]
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

        pokemon_types_list = pokemon_types_df[pokemon_types_df["pokemon_id"] == pokemon_id]["type_id"].tolist()
        type_names = ", ".join(types_df[types_df["id"].isin(pokemon_types_list)]["identifier"].tolist())

        stats_list = pokemon_stats_df[pokemon_stats_df["pokemon_id"] == pokemon_id][["stat_id", "base_stat"]]

        evolution_chain_id = pokemon_species_df[pokemon_species_df["id"] == pokemon_dexNum]["evolution_chain_id"].values[0]
        evolution_chain = pokemon_species_df[pokemon_species_df["evolution_chain_id"] == evolution_chain_id]

        # sort evolution chain by evolution order
        start_row = evolution_chain[evolution_chain["evolves_from_species_id"].isna()].sort_values("id").iloc[0]
        current_id = start_row["id"]

        order = [current_id]

        current_ids = [current_id]

        for current_id in current_ids:
            next_rows = evolution_chain[evolution_chain["evolves_from_species_id"] == current_id].sort_values("id")
            if next_rows.empty:
                continue
            
            for k in range(len(next_rows)):
                order.append(next_rows.iloc[k]["id"])
            current_ids.extend(next_rows["id"].tolist())



        evolution_chain_sorted = evolution_chain.set_index("id").loc[order].reset_index()
        ###

        evolution_chain_id_list = evolution_chain_sorted["id"].tolist()

        pokemon_evolution_line_list = []
        for pid in evolution_chain_id_list:
            pok = pokemon_df[pokemon_df["id"] == pid]
            if not pok.empty:
                name = pokemon_species_names_df[(pokemon_species_names_df["pokemon_species_id"] == pid)]
                name = name[name["local_language_id"] == language_id]
                if not name.empty:
                    name = name["name"].values[0]
                else:
                    name = pok["identifier"].values[0]
                pokemon_evolution_line_list.append({
                    "name": name,
                    "image": f"data/sprites/sprites/pokemon/{int(pid)}.png",
                    "dex_number": pok["species_id"].values[0]
                })






        pokemon_forms_list = pokemon_df[pokemon_df["species_id"] == pokemon_dexNum]["identifier"].tolist()


        pokemon_localized_name = pokemon_species_names_df[(pokemon_species_names_df["pokemon_species_id"] == pokemon_dexNum)]
        pokemon_localized_name = pokemon_localized_name[pokemon_localized_name["local_language_id"] == language_id]

        if not pokemon_localized_name.empty:
            pokemon_localized_name = pokemon_localized_name["name"].values[0]
        else:
            pokemon_localized_name = p["identifier"].capitalize()
        

        return {
            "name": pokemon_localized_name,
            "dex_number": p["species_id"],
            "image": f"data/sprites/sprites/pokemon/{int(p['id'])}.png",
            "cries": [f"data/cries/cries/pokemon/latest/{int(p['id'])}.ogg"],
            "types": type_names.split(", "),
            "base_stats": {
                "HP": stats_list[stats_list["stat_id"] == 1]["base_stat"].values[0],
                "Atk": stats_list[stats_list["stat_id"] == 2]["base_stat"].values[0],
                "Def": stats_list[stats_list["stat_id"] == 3]["base_stat"].values[0],
                "SpA": stats_list[stats_list["stat_id"] == 4]["base_stat"].values[0],
                "SpD": stats_list[stats_list["stat_id"] == 5]["base_stat"].values[0],
                "Spe": stats_list[stats_list["stat_id"] == 6]["base_stat"].values[0]
            },
            "evolution_line": pokemon_evolution_line_list,
            "forms": pokemon_forms_list,
        }

    @staticmethod
    def get_available_forms(identifier):

        if isinstance(identifier, str):
            try:
                dex = int(identifier)
                pokemon = pokemon_species_df[pokemon_species_df["id"] == dex]
            except ValueError:
                pokemon = pokemon_species_df[pokemon_species_df["identifier"].str.lower() == identifier.lower()]
        else:
            pokemon = pokemon_species_df[pokemon_species_df["id"] == identifier]
            dex = pokemon["id"].values[0] if not pokemon.empty else None

        if pokemon.empty:
            raise ValueError(f"Pokémon '{identifier}' not found")


        p = pokemon.iloc[0]
        p = pokemon_df[pokemon_df["id"] == p["id"]].iloc[0]

        pokemon_dexNum = p["species_id"]
        pokemon_forms_list = pokemon_df[pokemon_df["species_id"] == pokemon_dexNum]["identifier"].tolist()
        return pokemon_forms_list
    

    @staticmethod
    def get_pokedex_flavor(identifier, language_id=9):


        if isinstance(identifier, str):
            try:
                id = int(identifier)
                pokemon = pokemon_df[pokemon_df["id"] == id]
            except ValueError:
                pokemon = pokemon_df[pokemon_df["identifier"].str.lower() == identifier.lower()]
        else:
            pokemon = pokemon_df[pokemon_df["id"] == identifier]
            dex = pokemon["id"].values[0] if not pokemon.empty else None

        if pokemon.empty:
            raise ValueError(f"Pokémon '{identifier}' not found")


        p = pokemon.iloc[0]
        p = pokemon_df[pokemon_df["id"] == p["id"]].iloc[0]
        pokemon_dexNum = p["species_id"]


        flavor_dataframe = pokemon_species_flavor_text_df[pokemon_species_flavor_text_df["language_id"] == language_id]
        flavor_dataframe = flavor_dataframe[flavor_dataframe["species_id"] == pokemon_dexNum]


        versions_list = versions_df[versions_df["id"].isin(flavor_dataframe["version_id"].values.tolist())]["identifier"].tolist()
        flavor_texts_list = flavor_dataframe["flavor_text"].values.tolist()


        return {
            "versions": versions_list,
            "flavor_texts": flavor_texts_list
        }



