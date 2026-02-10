from pokedex.pokedex_core import PokedexAPI


def test_get_pokemon():
    api_instance = PokedexAPI()
    result = api_instance.get_pokemon("pikachu")
    assert isinstance(result, dict)
