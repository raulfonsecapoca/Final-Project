"""This module shows you how you can construct a nice documentation with
sphinx and the right syntaxe for docstrings.
"""

import numpy as np
import pandas as pd

pokemon_df = pd.read_csv("data/csv/pokemon.csv")
pokemon_evolution_df = pd.read_csv("data/csv/pokemon_evolution.csv")
pokemon_types_df = pd.read_csv("data/csv/pokemon_types.csv")
types_df = pd.read_csv("data/csv/types.csv")

class typed_function:


    pokemon_df = pd.read_csv("data/csv/pokemon.csv")
    pokemon_evolution_df = pd.read_csv("data/csv/pokemon_evolution.csv")
    pokemon_types_df = pd.read_csv("data/csv/pokemon_types.csv")
    types_df = pd.read_csv("data/csv/types.csv")

    dexNum = 25

    pokemonListSearch = pokemon_df[pokemon_df["species_id"] == dexNum]
    print(pokemonListSearch)



    @staticmethod
    def get_pokemon(identifier, form=None):
        # identifier pode ser número (25) ou nome ("pikachu")
        if isinstance(identifier, str):
            try:
                dex = int(identifier)
                pokemon = pokemon_df[pokemon_df["species_id"] == dex]
            except ValueError:
                pokemon = pokemon_df[pokemon_df["identifier"].str.lower() == identifier.lower()]
        else:
            pokemon = pokemon_df[pokemon_df["species_id"] == identifier]
            dex = pokemon["species_id"].values[0] if not pokemon.empty else None

        if pokemon.empty:
            raise ValueError(f"Pokémon '{identifier}' not found")
        

        p = pokemon.iloc[0]
        pokemon_id = p["id"]

        pokemon_types_list = pokemon_types_df[pokemon_types_df["pokemon_id"] == pokemon_id]["type_id"].tolist()
        type_names = ", ".join(types_df[types_df["id"].isin(pokemon_types_list)]["identifier"].tolist())

        return {
            "name": p["identifier"],
            "dex_number": p["species_id"],
            "image": f"data/sprites/sprites/pokemon/{int(p['species_id'])}.png",
            "cries": [f"data/cries/cries/pokemon/latest/{int(p['species_id'])}.ogg"],
            "types": type_names.split(", "),
            "base_stats": {
                "HP": 45,
                "Atk": 49,
                "Def": 49,
                "SpA": 65,
                "SpD": 65,
                "Spe": 45
            },
            "evolution_line": [
                {"name": "Pichu", "image": "data/sprites/sprites/pokemon/172.png"},
                {"name": "Pikachu", "image": "data/sprites/sprites/pokemon/25.png"},
                {"name": "Raichu", "image": "data/sprites/sprites/pokemon/26.png"},
            ],
            "forms": ["Base"],
        }

    @staticmethod
    def get_available_forms(identifier):
        return ["Base"]



