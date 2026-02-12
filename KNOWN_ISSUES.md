# Known Issues

## Ability Generation Chart

The generation chart aggregates data at the species level.

Alternative forms (e.g., Mega Evolutions or special battle forms) are included
in the total Pokémon count but are not displayed as separate slices in the chart,
since generation data is only available at the species level.

TODO: Support form-level generation logic if such metadata becomes available.


## Ability Name Collision

Some abilities share the same display name but have different descriptions
depending on the Pokémon form (e.g., Calyrex Ice Rider vs. Calyrex Shadow Rider).

The current implementation resolves abilities by name (string) rather than
by unique `ability_id`, which may return the first matching description found.

TODO: Refactor ability resolution to use `ability_id` instead of ability name.


## Incomplete Data

Some entries in the current dataset are incomplete.

### Items

Certain items exist in the database (name available in one or more languages),
but associated metadata such as image and description is missing.

Examples:
- Auspicious Armor
- Malicious Armor

### Pokémon and Forms

Some Pokémon forms and recently introduced content lack full asset support
(e.g., image, cry, or additional metadata).

Examples:
- Several Pikachu costume variants (e.g., cap forms) have entries but no sprite.
- Newly introduced Mega Evolutions from Pokémon Legends: Z-A currently lack
  sprite and audio data.

### Pokédex Entries

Many Pokémon have missing Pokédex flavor text entries, especially in
non-English languages.

Some Pokémon — particularly more recent ones — may lack Pokédex entries
entirely across all languages and game versions in the current dataset.