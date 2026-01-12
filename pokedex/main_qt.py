# main_qt.py
# """
# Pokédex app UI using PySide6.

# This file expects pokedex.my_module.typed_function to expose:

# - get_pokemon(identifier: str, form: str | None = None, language_id: int = 9) -> dict
#   - returning keys:
#     - name, dex_number, image, cries (list[str]), types (list[int|str]),
#     - base_stats (dict[str,int]), evolution_line (list[dict{name,image,dex_number}]),
#     - forms (list[str]|optional)
#   - NEW keys recommended:
#     - abilities (list[str]|optional)
#     - egg_groups (list[str]|optional)

# - (optional) get_available_forms(identifier) -> list[str]
# - (optional) get_pokedex_flavor(identifier: str, language_id: int = 9)
#   returning {"versions": list, "flavor_texts": list}

# NEW (stubs you implement for the UI to fully work):
# - get_ability_description(ability: str, language_id: int = 9) -> str
# - get_all_types(language_id: int = 9) -> list[str] or list[tuple[str,str]]
# - get_all_abilities(language_id: int = 9) -> list[str] or list[tuple[str,str]]
# - get_all_egg_groups(language_id: int = 9) -> list[str] or list[tuple[str,str]]
# - get_stat_rank(identifier: str, stat_key: str, language_id: int = 9, type_filter: str | None = None) -> dict
# - count_pokemon_with_ability(ability: str, type_filter: str | None = None) -> int
# - count_pokemon_in_egg_group(egg_group: str, type_filter: str | None = None) -> int
# """

import os
import sys
from itertools import zip_longest
from pathlib import Path

import pandas as pd
import requests
from PySide6.QtCore import QSize, QStringListModel, Qt, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pokedex.my_module import PokedexAPI as api  # your data provider

# ---- CSVs for language metadata + localized Pokémon names (autocomplete) ------
language_names_df = pd.read_csv("data/csv/language_names.csv")
languages_df = pd.read_csv("data/csv/languages.csv")
pokemon_species_df = pd.read_csv("data/csv/pokemon_species.csv")
pokemon_species_names_df = pd.read_csv(
    "data/csv/pokemon_species_names.csv"
)  # localized names

BASE_DIR = Path(__file__).resolve().parent.parent  # Final-Project/
TYPE_ICON_DIR = (
    BASE_DIR
    / "data"
    / "sprites"
    / "sprites"
    / "types"
    / "generation-ix"
    / "scarlet-violet"
)


# ---- Helpers -----------------------------------------------------------------


def _load_pixmap(path_or_url: str, max_size: QSize | None = QSize(256, 256)) -> QPixmap:
    """Load image from local path or URL into QPixmap; optionally scale preserving aspect ratio."""
    try:
        if path_or_url.startswith(("http://", "https://")):
            resp = requests.get(path_or_url, timeout=10)
            resp.raise_for_status()
            pm = QPixmap()
            pm.loadFromData(resp.content)
        else:
            pm = QPixmap(path_or_url)

        if not pm or pm.isNull():
            return QPixmap()

        if max_size is not None:
            pm = pm.scaled(
                max_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return pm
    except Exception:
        return QPixmap()


def _lang_autonym(lang_id: int) -> str:
    """
    Prefer the autonym (language name in its own language): local_language_id == language_id.
    Fallback to English exonym (local_language_id == 9). Final fallback: the numeric id.
    """
    df = language_names_df
    row = df[(df["language_id"] == lang_id) & (df["local_language_id"] == lang_id)]
    if not row.empty:
        return str(row["name"].iloc[0])
    row = df[(df["language_id"] == lang_id) & (df["local_language_id"] == 9)]
    if not row.empty:
        return str(row["name"].iloc[0])
    return str(lang_id)


# ---- Main Window --------------------------------------------------------------


class PokedexWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pokédex")
        self.setMinimumSize(980, 720)
        self.setWindowIcon(QIcon("data/sprites/sprites/items/poke-ball.png"))

        # Playback
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)

        # State
        self.current_identifier: str | None = None
        self.current_data: dict = {}
        self.current_cry_index: int = 0

        # Pokédex flavor state
        self._flavor_versions: list[str] = []
        self._flavor_texts: list[str] = []

        # Forms combo state (frozen order)
        self._forms_cache_identifier = None
        self._forms_cache_list: list[str] | None = None
        self._forms_order: list[str] = []

        # Language (default English id=9)
        self.current_language_id = 9
        official_ids: list[int] = (
            languages_df[languages_df["official"] == 1]
            .sort_values("order")["id"]
            .astype(int)
            .tolist()
        )
        self._official_langs: list[tuple[int, str]] = [
            (lid, _lang_autonym(lid)) for lid in official_ids
        ]

        # ---------------- Top bar (shared) ----------------
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText(
            "Enter Pokémon name or number (e.g., pikachu or 25)"
        )
        self.btn_load = QPushButton("Load")

        self.form_combo = QComboBox()
        self.form_combo.setEnabled(False)
        self.form_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.form_combo.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )
        self.form_combo.setMinimumContentsLength(12)

        self.btn_play_cry = QPushButton("Play Cry")
        self.btn_play_cry.setEnabled(False)

        top_row = QHBoxLayout()
        top_row.addWidget(self.input_name, 3)
        top_row.addWidget(self.btn_load, 0)
        top_row.addSpacing(12)
        top_row.addWidget(QLabel("Form:"), 0)
        top_row.addWidget(self.form_combo, 0)
        top_row.addSpacing(12)
        top_row.addWidget(self.btn_play_cry, 0)

        # ---------------- Language bar ----------------
        self.lang_row = QHBoxLayout()
        self._build_language_bar(self.lang_row)

        # ---------------- Main tabs ----------------
        self.tabs = QTabWidget()
        self.tab_pokedex = QWidget()
        self.tab_stats = QWidget()
        self.tabs.addTab(self.tab_pokedex, "Pokédex")
        self.tabs.addTab(self.tab_stats, "Statistics")

        # Build tab contents
        self._build_pokedex_tab()
        self._build_statistics_tab()

        # ---------------- Root layout ----------------
        root = QVBoxLayout(self)
        root.addLayout(top_row)
        root.addLayout(self.lang_row)
        root.addSpacing(6)
        root.addWidget(self.tabs, 1)

        # ---------------- Signals ----------------
        self.btn_load.clicked.connect(self._on_load_clicked)
        self.btn_play_cry.clicked.connect(self._on_play_cry_clicked)
        self.form_combo.currentTextChanged.connect(self._on_form_changed)
        self.input_name.returnPressed.connect(self._on_load_clicked)

        # Autocomplete (top bar)
        self._init_pokemon_autocomplete()

        # Fill statistics catalogs (types + ability/egg autocompletes)
        self._init_statistics_catalogs()

    # -------------------------------------------------------------------------
    # Build: Pokédex tab
    # -------------------------------------------------------------------------

    def _build_pokedex_tab(self):
        # Left column
        self.lbl_sprite = QLabel()
        self.lbl_sprite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sprite.setFrameShape(QFrame.Shape.Panel)
        self.lbl_sprite.setFrameShadow(QFrame.Shadow.Sunken)
        self.lbl_sprite.setMinimumSize(256, 256)

        self.lbl_name = QLabel("<b>Name</b>")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_dex = QLabel("Dex #: —")
        self.lbl_dex.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.types_row = QHBoxLayout()
        self.types_row.addStretch()

        # NEW: Abilities (combo + description)
        self.ability_group = QGroupBox("Abilities")
        self.ability_group.setEnabled(False)

        self.ability_combo = QComboBox()
        self.ability_combo.setEnabled(False)
        self.ability_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self.ability_combo.currentIndexChanged.connect(self._on_ability_changed)

        self.lbl_ability_desc = QLabel("—")
        self.lbl_ability_desc.setWordWrap(True)
        self.lbl_ability_desc.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_ability_desc.setMinimumHeight(70)

        ag = QVBoxLayout()
        ag.addWidget(self.ability_combo)
        ag.addWidget(self.lbl_ability_desc)
        self.ability_group.setLayout(ag)

        # NEW: Egg groups
        self.egg_group_box = QGroupBox("Egg Groups")
        self.egg_group_box.setEnabled(False)

        self.lbl_egg_groups = QLabel("—")
        self.lbl_egg_groups.setWordWrap(True)
        eg = QVBoxLayout()
        eg.addWidget(self.lbl_egg_groups)
        self.egg_group_box.setLayout(eg)

        # Pokédex flavor
        self.dex_group = QGroupBox("Pokédex Entry")
        self.dex_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )

        self.dex_combo = QComboBox()
        self.dex_combo.setEnabled(False)
        self.dex_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.dex_combo.currentIndexChanged.connect(self._on_pokedex_version_changed)

        self.lbl_flavor = QLabel("—")
        self.lbl_flavor.setWordWrap(True)
        self.lbl_flavor.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_flavor.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        self.lbl_flavor.setMinimumHeight(140)

        dex_layout = QVBoxLayout()
        row = QHBoxLayout()
        row.addWidget(QLabel("Version:"))
        row.addWidget(self.dex_combo, 1)
        dex_layout.addLayout(row)
        dex_layout.addWidget(self.lbl_flavor)
        self.dex_group.setLayout(dex_layout)
        self.dex_group.setEnabled(False)

        left_col = QVBoxLayout()
        left_col.addWidget(self.lbl_sprite)
        left_col.addSpacing(8)
        left_col.addWidget(self.lbl_name)
        left_col.addWidget(self.lbl_dex)
        left_col.addLayout(self.types_row)
        left_col.addSpacing(8)
        left_col.addWidget(self.ability_group)
        left_col.addWidget(self.egg_group_box)
        left_col.addWidget(self.dex_group)
        left_col.addStretch()

        # Right column (stats + evolution)
        self.stats_grid = QGridLayout()
        self.stats_labels = {}
        for r, s in enumerate(["HP", "Atk", "Def", "SpA", "SpD", "Spe"]):
            k = QLabel(f"{s}:")
            v = QLabel("—")
            self.stats_labels[s] = v
            self.stats_grid.addWidget(k, r, 0, alignment=Qt.AlignmentFlag.AlignRight)
            self.stats_grid.addWidget(v, r, 1, alignment=Qt.AlignmentFlag.AlignLeft)

        stats_group = QGroupBox("Base Stats")
        sg_layout = QVBoxLayout()
        sg_layout.addLayout(self.stats_grid)
        stats_group.setLayout(sg_layout)

        self.evo_container = QWidget()
        self.evo_row = QHBoxLayout(self.evo_container)
        self.evo_row.setContentsMargins(0, 0, 0, 0)
        self.evo_row.setSpacing(16)
        self.evo_row.addStretch()

        evo_scroll = QScrollArea()
        evo_scroll.setWidgetResizable(True)
        evo_scroll.setWidget(self.evo_container)

        evo_group = QGroupBox("Evolution Line")
        el = QVBoxLayout()
        el.addWidget(evo_scroll)
        evo_group.setLayout(el)

        right_col = QVBoxLayout()
        right_col.addWidget(stats_group)
        right_col.addWidget(evo_group, 1)

        # Assemble
        main_row = QHBoxLayout()
        main_row.addLayout(left_col, 1)
        main_row.addLayout(right_col, 2)

        tab_layout = QVBoxLayout(self.tab_pokedex)
        tab_layout.addLayout(main_row, 1)

    # -------------------------------------------------------------------------
    # Build: Statistics tab + subtabs
    # -------------------------------------------------------------------------

    def _build_statistics_tab(self):
        self.stats_tabs = QTabWidget()
        self.stats_tab_pokemon = QWidget()
        self.stats_tab_egg = QWidget()
        self.stats_tab_abilities = QWidget()

        self.stats_tabs.addTab(self.stats_tab_pokemon, "Pokemon")
        self.stats_tabs.addTab(self.stats_tab_egg, "Egg Groups")
        self.stats_tabs.addTab(self.stats_tab_abilities, "Abilities")

        # ---------------- Subtab: Pokemon (Ranking) ----------------
        self.rank_group = QGroupBox("Stat Ranking (uses the top search bar)")
        hint = QLabel(
            "Use the top search bar to choose the Pokémon, then compute rank here."
        )
        hint.setWordWrap(True)

        self.rank_stat_combo = QComboBox()
        self.rank_stat_combo.addItems(["HP", "Atk", "Def", "SpA", "SpD", "Spe"])

        self.rank_type_filter_combo = QComboBox()
        self.rank_type_filter_combo.addItem("All types", userData=None)

        self.btn_compute_rank = QPushButton("Compute Rank")
        self.lbl_rank_result = QLabel("—")
        self.lbl_rank_result.setWordWrap(True)

        rg = QGridLayout()
        rg.addWidget(hint, 0, 0, 1, 2)
        rg.addWidget(QLabel("Stat:"), 1, 0)
        rg.addWidget(self.rank_stat_combo, 1, 1)
        rg.addWidget(QLabel("Type filter:"), 2, 0)
        rg.addWidget(self.rank_type_filter_combo, 2, 1)
        rg.addWidget(self.btn_compute_rank, 3, 0, 1, 2)
        rg.addWidget(self.lbl_rank_result, 4, 0, 1, 2)
        self.rank_group.setLayout(rg)

        pokemon_layout = QVBoxLayout(self.stats_tab_pokemon)
        pokemon_layout.addWidget(self.rank_group)
        pokemon_layout.addStretch()

        # ---------------- Subtab: Abilities (search bar) ----------------
        self.ability_stats_group = QGroupBox("Ability Distribution")
        self.ability_search = QLineEdit()
        self.ability_search.setPlaceholderText("Search ability (type to autocomplete)")

        self.ability_type_filter_combo = QComboBox()
        self.ability_type_filter_combo.addItem("All types", userData=None)

        self.btn_count_ability = QPushButton("Count Pokémon With Ability")
        self.lbl_ability_count = QLabel("—")
        self.lbl_ability_count.setWordWrap(True)

        ag = QGridLayout()
        ag.addWidget(QLabel("Ability:"), 0, 0)
        ag.addWidget(self.ability_search, 0, 1)
        ag.addWidget(QLabel("Type filter:"), 1, 0)
        ag.addWidget(self.ability_type_filter_combo, 1, 1)
        ag.addWidget(self.btn_count_ability, 2, 0, 1, 2)
        ag.addWidget(self.lbl_ability_count, 3, 0, 1, 2)
        self.ability_stats_group.setLayout(ag)

        abilities_layout = QVBoxLayout(self.stats_tab_abilities)
        abilities_layout.addWidget(self.ability_stats_group)
        abilities_layout.addStretch()

        # ---------------- Subtab: Egg Groups (search bar) ----------------
        self.egg_stats_group = QGroupBox("Egg Group Distribution")
        self.egg_search = QLineEdit()
        self.egg_search.setPlaceholderText("Search egg group (type to autocomplete)")

        self.egg_type_filter_combo = QComboBox()
        self.egg_type_filter_combo.addItem("All types", userData=None)

        self.btn_count_egg = QPushButton("Count Pokémon In Egg Group")
        self.lbl_egg_count = QLabel("—")
        self.lbl_egg_count.setWordWrap(True)

        eg = QGridLayout()
        eg.addWidget(QLabel("Egg group:"), 0, 0)
        eg.addWidget(self.egg_search, 0, 1)
        eg.addWidget(QLabel("Type filter:"), 1, 0)
        eg.addWidget(self.egg_type_filter_combo, 1, 1)
        eg.addWidget(self.btn_count_egg, 2, 0, 1, 2)
        eg.addWidget(self.lbl_egg_count, 3, 0, 1, 2)
        self.egg_stats_group.setLayout(eg)

        egg_layout = QVBoxLayout(self.stats_tab_egg)
        egg_layout.addWidget(self.egg_stats_group)
        egg_layout.addStretch()

        # Assemble Statistics tab
        tab_layout = QVBoxLayout(self.tab_stats)
        tab_layout.addWidget(self.stats_tabs, 1)

        # Signals
        self.btn_compute_rank.clicked.connect(self._on_compute_rank_clicked)
        self.btn_count_ability.clicked.connect(self._on_count_ability_clicked)
        self.btn_count_egg.clicked.connect(self._on_count_egg_clicked)

        self.ability_search.returnPressed.connect(self._on_count_ability_clicked)
        self.egg_search.returnPressed.connect(self._on_count_egg_clicked)

    # -------------------------------------------------------------------------
    # Language bar
    # -------------------------------------------------------------------------

    def _build_language_bar(self, layout: QHBoxLayout):
        layout.addWidget(QLabel("Language:"))
        self._lang_buttons: list[QToolButton] = []

        for lang_id, display in self._official_langs:
            btn = QToolButton()
            btn.setText(display)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            if lang_id == self.current_language_id:
                btn.setChecked(True)
            btn.clicked.connect(
                lambda _=False, lid=lang_id: self._on_language_selected(lid)
            )
            self._lang_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

    def _on_language_selected(self, lang_id: int):
        if self.current_language_id == lang_id:
            return

        self.current_language_id = lang_id

        # Refresh top autocomplete
        self._init_pokemon_autocomplete()

        # Refresh statistics catalogs (types + ability/egg autocompletes)
        self._init_statistics_catalogs()

        # Reload current Pokémon if any
        if self.current_identifier:
            current_form = self.form_combo.currentText().strip() or None
            self._load_pokemon_data(
                identifier=self.current_identifier, form=current_form
            )

    # -------------------------------------------------------------------------
    # Top autocomplete (Pokémon names)
    # -------------------------------------------------------------------------

    def _init_pokemon_autocomplete(self):
        all_names = self._get_all_pokemon_names()
        self._all_pokemon_names = sorted(set(all_names), key=str.casefold)

        self._pokemon_completer_model = QStringListModel(self._all_pokemon_names, self)
        self._pokemon_completer = QCompleter(self._pokemon_completer_model, self)
        self._pokemon_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._pokemon_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )

        self.input_name.setCompleter(self._pokemon_completer)
        self.input_name.textEdited.connect(self._on_pokemon_search_text_edited)

    def _get_all_pokemon_names(self) -> list[str]:
        lang = self.current_language_id
        df = pokemon_species_names_df[
            pokemon_species_names_df["local_language_id"] == lang
        ]
        if df.empty:
            return pokemon_species_df["identifier"].str.capitalize().tolist()
        return df["name"].tolist()

    def _on_pokemon_search_text_edited(self, text: str):
        pattern = text.strip().casefold()
        if not pattern:
            self._pokemon_completer_model.setStringList([])
            return
        matches = [
            name
            for name in self._all_pokemon_names
            if name.casefold().startswith(pattern)
        ]
        self._pokemon_completer_model.setStringList(matches[:10])

    # -------------------------------------------------------------------------
    # Data loading (Pokédex tab)
    # -------------------------------------------------------------------------

    def _on_load_clicked(self):
        ident = self.input_name.text().strip()
        if not ident:
            QMessageBox.warning(
                self, "Pokédex", "Please type a Pokémon name or number."
            )
            return
        self.current_identifier = ident
        self._load_pokemon_data(identifier=ident, form=None)

    def _on_form_changed(self, form_text: str):
        if not self.current_identifier:
            return
        self._load_pokemon_data(
            identifier=self.current_identifier, form=(form_text or None)
        )

    def _load_pokemon_data(self, identifier: str, form: str | None):
        """Call API and bind to UI; always pass current language_id."""
        try:
            data = api.get_pokemon(
                identifier, form=form, language_id=self.current_language_id
            )
            if not isinstance(data, dict):
                raise ValueError("pokedex.get_pokemon must return a dict")

            self.current_data = data

            self._bind_header(data)
            self._bind_types(data.get("types", []))
            self._bind_stats(data.get("base_stats", {}))
            self._bind_evolution_line(data.get("evolution_line", []))
            self._bind_forms(identifier, data)
            self._bind_pokedex_flavor(identifier)

            # NEW binders
            self._bind_abilities(
                data.get("abilities") or [],
                data.get("is_hidden_ability") or [],
            )

            self._bind_egg_groups(data.get("egg_groups") or [])

            cries = data.get("cries") or []
            self.btn_play_cry.setEnabled(bool(cries))
            self.current_cry_index = 0

        except Exception as e:
            QMessageBox.critical(self, "Error loading Pokémon", str(e))

    # -------------------------------------------------------------------------
    # Pokédex binders
    # -------------------------------------------------------------------------

    def _bind_header(self, data: dict):
        name = data.get("name", "Unknown")
        dex = data.get("dex_number", "—")
        self.lbl_name.setText(f"<b>{name}</b>")
        self.lbl_dex.setText(f"Dex #: {dex}")

        image = data.get("image")
        pm = _load_pixmap(image) if image else QPixmap()
        if pm.isNull():
            self.lbl_sprite.setText("No image")
            self.lbl_sprite.setPixmap(QPixmap())
        else:
            self.lbl_sprite.setPixmap(pm)
            self.lbl_sprite.setText("")

    def _bind_types(self, types: list):
        """Show types as icons, expects numeric ids or strings."""
        while self.types_row.count() > 0:
            item = self.types_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self.types_row.addStretch()

        for t in types:
            try:
                type_id = int(t)
            except (TypeError, ValueError):
                lbl = QLabel(str(t))
                self.types_row.addWidget(lbl)
                continue

            icon_path = TYPE_ICON_DIR / f"{type_id}.png"
            lbl = QLabel()
            pm = QPixmap(str(icon_path))
            if pm.isNull():
                lbl.setText(str(type_id))
            else:
                lbl.setPixmap(pm)
            self.types_row.addWidget(lbl)

        self.types_row.addStretch()

    def _bind_stats(self, stats: dict):
        for key, lbl in self.stats_labels.items():
            val = stats.get(key) or stats.get(key.lower()) or "—"
            lbl.setText(str(val))

    def _bind_evolution_line(self, evo_list: list[dict]):
        while self.evo_row.count() > 0:
            item = self.evo_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for node in evo_list:
            w = self._make_evo_card(
                name=node.get("name", "?"),
                image=node.get("image"),
                dex_number=node.get("dex_number"),
            )
            self.evo_row.addWidget(w)

        self.evo_row.addStretch()

    def _make_evo_card(
        self, name: str, image: str | None, dex_number: int | None
    ) -> QWidget:
        box = QVBoxLayout()
        img = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        pm = _load_pixmap(image, QSize(96, 96)) if image else QPixmap()
        img.setPixmap(pm) if not pm.isNull() else img.setText("—")

        nm = QLabel(name, alignment=Qt.AlignmentFlag.AlignCenter)
        nm.setWordWrap(True)

        dx = QLabel(
            f"Dex #: {dex_number}" if dex_number is not None else "Dex #: —",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        btn = QPushButton("View")
        if dex_number is not None:
            btn.clicked.connect(
                lambda: self._load_pokemon_data(identifier=str(dex_number), form=None)
            )
        else:
            btn.clicked.connect(
                lambda: self._load_pokemon_data(identifier=name, form=None)
            )

        cont = QWidget()
        box.addWidget(img)
        box.addWidget(nm)
        box.addWidget(dx)
        box.addWidget(btn)
        cont.setLayout(box)
        cont.setMinimumWidth(120)
        return cont

    # -------- Forms combo: stable (frozen) --------
    def _bind_forms(self, identifier: str, data: dict):
        if self._forms_cache_identifier != identifier:
            self._forms_order = []

        forms = data.get("forms")
        if forms is None and hasattr(api, "get_available_forms"):
            try:
                forms = api.get_available_forms(identifier)
            except Exception:
                forms = None

        forms = [str(f).strip() for f in (forms or []) if str(f).strip()]
        dedup_forms = list(dict.fromkeys(forms))

        if not self._forms_order:
            self._forms_order = dedup_forms[:]

        self._forms_cache_identifier = identifier
        self._forms_cache_list = self._forms_order[:]

        prev_choice = (
            self.form_combo.currentText().strip() if self.form_combo.count() > 0 else ""
        )

        self.form_combo.blockSignals(True)
        self.form_combo.clear()
        for f in self._forms_order:
            self.form_combo.addItem(f)

        self.form_combo.setEnabled(bool(self._forms_order))

        if prev_choice and prev_choice in self._forms_order:
            self.form_combo.setCurrentText(prev_choice)
        elif self._forms_order:
            self.form_combo.setCurrentText(self._forms_order[0])

        self.form_combo.blockSignals(False)

    # -------- Pokédex flavor --------
    def _bind_pokedex_flavor(self, identifier: str):
        self._flavor_versions = []
        self._flavor_texts = []

        if not hasattr(api, "get_pokedex_flavor"):
            self.dex_group.setEnabled(False)
            self.dex_combo.clear()
            self.lbl_flavor.setText("—")
            return

        try:
            res = api.get_pokedex_flavor(
                identifier, language_id=self.current_language_id
            )
            versions = res.get("versions") or []
            texts = res.get("flavor_texts") or []

            n = min(len(versions), len(texts))
            versions = [str(v) for v in versions[:n]]
            texts = [str(t).replace("\n", " ").replace("\f", " ") for t in texts[:n]]

            if n == 0:
                self.dex_group.setEnabled(False)
                self.dex_combo.clear()
                self.lbl_flavor.setText("—")
                return

            self._flavor_versions = versions
            self._flavor_texts = texts

            self.dex_combo.blockSignals(True)
            self.dex_combo.clear()
            for i, v in enumerate(versions):
                self.dex_combo.addItem(v, userData=i)
            self.dex_combo.setCurrentIndex(0)
            self.dex_combo.blockSignals(False)

            self.lbl_flavor.setText(texts[0])
            self.dex_group.setEnabled(True)
            self.dex_combo.setEnabled(True)

        except Exception:
            self.dex_group.setEnabled(False)
            self.dex_combo.clear()
            self.lbl_flavor.setText("—")

    def _on_pokedex_version_changed(self, idx: int):
        if not self._flavor_texts:
            return
        if 0 <= idx < len(self._flavor_texts):
            self.lbl_flavor.setText(self._flavor_texts[idx])

    # -------- NEW: Abilities + description --------

    def _bind_abilities(self, abilities: list[str], hidden_flags: list[bool]) -> None:
        self.ability_combo.blockSignals(True)
        self.ability_combo.clear()

        abilities_clean: list[str] = [
            str(a).strip() for a in (abilities or []) if str(a).strip()
        ]
        hidden_clean: list[bool] = [bool(x) for x in (hidden_flags or [])]

        if not abilities_clean:
            self.ability_group.setEnabled(False)
            self.ability_combo.setEnabled(False)
            self.lbl_ability_desc.setText("—")
            self.ability_combo.blockSignals(False)
            return

        for name_raw, hidden_raw in zip_longest(
            abilities_clean, hidden_clean, fillvalue=False
        ):
            name: str = str(name_raw)  # <- forces str for type checker
            is_hidden_bool: bool = bool(hidden_raw)

            display: str = f"{name} (Hidden)" if is_hidden_bool else name
            self.ability_combo.addItem(display, userData=(name, is_hidden_bool))

        self.ability_group.setEnabled(True)
        self.ability_combo.setEnabled(True)
        self.ability_combo.setCurrentIndex(0)
        self.ability_combo.blockSignals(False)

        self._update_ability_description()

    def _on_ability_changed(self, _idx: int):
        self._update_ability_description()

    def _update_ability_description(self) -> None:
        if self.ability_combo.count() == 0:
            self.lbl_ability_desc.setText("—")
            return

        data = self.ability_combo.currentData()

        # Expected: (ability_name, is_hidden_bool)
        if isinstance(data, tuple) and len(data) == 2:
            ability_name, is_hidden = data
            ability_str = str(ability_name).strip()
            is_hidden_bool = bool(is_hidden)
        else:
            # Fallback if old items exist
            ability_str = str(self.ability_combo.currentText()).strip()
            is_hidden_bool = False

        if not ability_str:
            self.lbl_ability_desc.setText("—")
            return

        if not hasattr(api, "get_ability_description"):
            self.lbl_ability_desc.setText("Ability description API not available.")
            return

        try:
            # Your API must accept (ability: str, is_hidden: bool, language_id: int)
            desc = api.get_ability_description(
                ability_str,
                is_hidden_bool,
                language_id=self.current_language_id,
            )

            if desc is None:
                self.lbl_ability_desc.setText("—")
                return

            desc_str = str(desc).replace("\n", " ").replace("\f", " ").strip()
            self.lbl_ability_desc.setText(desc_str if desc_str else "—")

        except Exception as e:
            self.lbl_ability_desc.setText(f"Error: {e}")

    # -------- NEW: Egg groups --------
    def _bind_egg_groups(self, egg_groups: list[str]):
        egg_groups = [str(e).strip() for e in (egg_groups or []) if str(e).strip()]
        if not egg_groups:
            self.egg_group_box.setEnabled(False)
            self.lbl_egg_groups.setText("—")
            return
        self.egg_group_box.setEnabled(True)
        self.lbl_egg_groups.setText(", ".join(egg_groups))

    # -------------------------------------------------------------------------
    # Media
    # -------------------------------------------------------------------------

    def _on_play_cry_clicked(self):
        cries = self.current_data.get("cries") or []
        if not cries:
            return
        url = cries[self.current_cry_index % len(cries)]
        self.current_cry_index += 1
        self._play_audio(url)

    def _play_audio(self, url_or_path: str):
        try:
            if url_or_path.startswith(("http://", "https://")):
                self.player.setSource(QUrl(url_or_path))
            else:
                self.player.setSource(QUrl.fromLocalFile(os.path.abspath(url_or_path)))
            self.audio.setVolume(0.8)
            self.player.play()
        except Exception as e:
            QMessageBox.warning(self, "Audio", f"Could not play cry:\n{e}")

    # -------------------------------------------------------------------------
    # Statistics catalogs + autocompletes (type filters + ability/egg search)
    # -------------------------------------------------------------------------

    def _init_statistics_catalogs(self):
        # Fill type filters
        self._fill_type_filter_combo(self.rank_type_filter_combo)
        self._fill_type_filter_combo(self.ability_type_filter_combo)
        self._fill_type_filter_combo(self.egg_type_filter_combo)

        # Abilities completer
        ability_names = self._fetch_catalog_strings("get_all_abilities")
        self._ability_model = QStringListModel(
            sorted(set(ability_names), key=str.casefold), self
        )
        self._ability_completer = QCompleter(self._ability_model, self)
        self._ability_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._ability_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self.ability_search.setCompleter(self._ability_completer)

        # Egg groups completer
        egg_names = self._fetch_catalog_strings("get_all_egg_groups")
        self._egg_model = QStringListModel(
            sorted(set(egg_names), key=str.casefold), self
        )
        self._egg_completer = QCompleter(self._egg_model, self)
        self._egg_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._egg_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.egg_search.setCompleter(self._egg_completer)

    def _fetch_catalog_strings(self, api_method_name: str) -> list[str]:
        """
        Accept either:
          - ["overgrow","blaze"]
          - [("65","Overgrow"), ("66","Blaze")] -> returns ["Overgrow","Blaze"]
        """
        if not hasattr(api, api_method_name):
            return []

        try:
            method = getattr(api, api_method_name)
            items = method(language_id=self.current_language_id)
        except Exception:
            return []

        out: list[str] = []
        for it in items or []:
            if isinstance(it, (list | tuple)) and len(it) >= 2:
                out.append(str(it[1]))
            else:
                out.append(str(it))
        return out

    def _fill_type_filter_combo(self, combo: QComboBox):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All types", userData=None)

        if hasattr(api, "get_all_types"):
            try:
                items = api.get_all_types(language_id=self.current_language_id)
                for it in items or []:
                    if isinstance(it, (list | tuple)) and len(it) >= 2:
                        key = str(it[0])
                        label = str(it[1])
                        combo.addItem(label, userData=key)
                    else:
                        s = str(it)
                        combo.addItem(s, userData=s)
            except Exception:
                pass

        combo.blockSignals(False)

    # -------------------------------------------------------------------------
    # Statistics actions
    # -------------------------------------------------------------------------

    def _on_compute_rank_clicked(self):
        # Uses TOP search bar (self.input_name), fallback to current_identifier
        ident = self.input_name.text().strip() or (self.current_identifier or "")
        if not ident:
            QMessageBox.warning(
                self, "Statistics", "Type a Pokémon name/number in the top bar first."
            )
            return

        stat_key = self.rank_stat_combo.currentText().strip()
        type_filter = self.rank_type_filter_combo.currentData()

        if not hasattr(api, "get_stat_rank"):
            self.lbl_rank_result.setText("TODO: implement api.get_stat_rank(...)")
            return

        try:
            res = api.get_stat_rank(
                identifier=ident,
                stat_key=stat_key,
                language_id=self.current_language_id,
                type_filter=type_filter,
            )
            rank = res.get("rank")
            total = res.get("total")
            value = res.get("value")
            self.lbl_rank_result.setText(
                f"{ident} • {stat_key} rank: {rank}/{total} (value: {value})"
            )
        except Exception as e:
            self.lbl_rank_result.setText(f"Error: {e}")

    def _on_count_ability_clicked(self):
        ability_text = self.ability_search.text().strip()
        if not ability_text:
            QMessageBox.warning(self, "Statistics", "Type an ability name first.")
            return

        type_filter = self.ability_type_filter_combo.currentData()

        if not hasattr(api, "count_pokemon_with_ability"):
            self.lbl_ability_count.setText(
                "TODO: implement api.count_pokemon_with_ability(...)"
            )
            return

        try:
            n = api.count_pokemon_with_ability(ability_text, type_filter=type_filter)
            self.lbl_ability_count.setText(f"Pokémon with '{ability_text}': {n}")
        except Exception as e:
            self.lbl_ability_count.setText(f"Error: {e}")

    def _on_count_egg_clicked(self):
        egg_text = self.egg_search.text().strip()
        if not egg_text:
            QMessageBox.warning(self, "Statistics", "Type an egg group name first.")
            return

        type_filter = self.egg_type_filter_combo.currentData()

        if not hasattr(api, "count_pokemon_in_egg_group"):
            self.lbl_egg_count.setText(
                "TODO: implement api.count_pokemon_in_egg_group(...)"
            )
            return

        try:
            n = api.count_pokemon_in_egg_group(egg_text, type_filter=type_filter)
            self.lbl_egg_count.setText(f"Pokémon in '{egg_text}': {n}")
        except Exception as e:
            self.lbl_egg_count.setText(f"Error: {e}")


# ---- Entrypoint ---------------------------------------------------------------


def run():
    r"""This is a typed function.
    This docstring is made so that it renders nicely on sphinx. It features notes,
    arguments, cross references (here, to numpy documentation), maths and examples.

    Notes:
        - This is a section with multiple notes
        - This second note has maths! :math:`p \in \mathbb{N}`

    .. math::
        :label: equation1

        D = \sum_{0 \le i < p} \alpha_i

    Args:
        a: first parameter, its description is really, and fits in
            two lines (note the indentation). The object must be a :obj:`np.ndarray`
        b: second parameter. Defaults to empty string.

    Examples
        >>> typed_function(np.zeros(10))
        False

        >>> typed_function(
        ...     np.zeros(10),
        ...     "hello"
        ... )
        False

    Returns:
        Always return False, it's not a very interesting function. See :eq:`equation1`
        for some more maths.
    """
    app = QApplication(sys.argv)
    w = PokedexWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    run()
