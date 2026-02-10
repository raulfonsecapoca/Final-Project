"""
Pokédex GUI (PySide6).

This module implements the Qt user interface for the Pokédex project.
All domain data is provided by :class:`pokedex.pokedex_core.PokedexAPI` (imported as ``api``).

The UI is split into two main tabs:
* Pokédex: Pokémon details (sprite, types, stats, evolution, flavor, abilities).
* Statistics: charts (type/gen/egg/histogram) and ability lookup.
"""

import math
import os
import sys
from itertools import zip_longest
from pathlib import Path

import pandas as pd
import requests
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QPieSlice,
    QValueAxis,
)
from PySide6.QtCore import QMargins, QSize, QStringListModel, Qt, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
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

from pokedex.pokedex_core import PokedexAPI as api  # your data provider

# ---- CSVs for language metadata + localized Pokémon names (autocomplete) ------

# Path setup (works on Windows and Linux)
MODULE_DIR = Path(__file__).resolve().parent  # .../pokedex
PROJECT_ROOT = MODULE_DIR.parent  # .../Final Project
DATA_DIR = PROJECT_ROOT / "data" / "csv"


def _read_csv(filename: str) -> pd.DataFrame:
    path = (DATA_DIR / filename).resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"CSV file not found: {path}\nExpected relative to project root: {DATA_DIR}"
        )
    return pd.read_csv(path)


language_names_df = _read_csv("language_names.csv")
languages_df = _read_csv("languages.csv")
pokemon_species_df = _read_csv("pokemon_species.csv")
pokemon_species_names_df = _read_csv("pokemon_species_names.csv")  # localized names

# ---- CSVs for item-name resolution from item sprite identifier (for evo click) ----
items_df = _read_csv("items.csv")
item_names_df = _read_csv("item_names.csv")

TYPE_ICON_DIR = (
    PROJECT_ROOT
    / "data"
    / "sprites"
    / "sprites"
    / "types"
    / "generation-ix"
    / "scarlet-violet"
)

# Type identifiers in the canonical Pokédex order (type_id 1..18).
TYPE_IDENTIFIERS: list[str] = [
    "normal",
    "fighting",
    "flying",
    "poison",
    "ground",
    "rock",
    "bug",
    "ghost",
    "steel",
    "fire",
    "water",
    "grass",
    "electric",
    "psychic",
    "ice",
    "dragon",
    "dark",
    "fairy",
]


# ---- Helpers -----------------------------------------------------------------


def _resolve_asset_path(path_or_url: str) -> str:
    """
    Resolve asset references (paths) coming from the API/UI.

    This fixes image/audio loading when the application is launched with a different
    current working directory (CWD).

    Rules:
    - If it's an HTTP(S) URL, return as-is.
    - If it's an absolute filesystem path, return as-is.
    - Otherwise, treat it as PROJECT_ROOT-relative (e.g., "data/...").
    """
    s = str(path_or_url).strip()
    if not s:
        return ""

    if s.startswith(("http://", "https://")):
        return s

    p = Path(s)
    if p.is_absolute():
        return str(p)

    return str((PROJECT_ROOT / p).resolve())


def _load_pixmap(path_or_url: str, max_size: QSize | None = QSize(256, 256)) -> QPixmap:
    """
    Load image from local path or URL into QPixmap; optionally scale preserving aspect ratio.

    Helper method used by the UI layer.

    Parameters
    ----------
    path_or_url: Any
        Value provided by Qt (signal) or by the caller.
    max_size: Any
        Value provided by Qt (signal) or by the caller.

    Notes
    -----
    Supports both local file paths and HTTP(S) URLs. Returns an empty ``QPixmap`` on failure.
    """
    try:
        resolved = _resolve_asset_path(path_or_url)
        if not resolved:
            return QPixmap()

        if resolved.startswith(("http://", "https://")):
            resp = requests.get(resolved, timeout=10)
            resp.raise_for_status()
            pm = QPixmap()
            pm.loadFromData(resp.content)
        else:
            pm = QPixmap(resolved)

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

    Helper method used by the UI layer.

    Parameters
    ----------
    lang_id: Any
        Value provided by Qt (signal) or by the caller.
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
    """
    Main window of the Pokédex Qt application.

    This widget assembles the full GUI, including the Pokédex and Statistics tabs,
    and delegates domain queries to :class:`pokedex.pokedex_core.PokedexAPI`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pokédex")
        self.setMinimumSize(980, 720)
        self.setWindowIcon(
            QIcon(_resolve_asset_path("data/sprites/sprites/items/poke-ball.png"))
        )

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

        # Fill statistics catalogs (types + ability autocomplete + items autocomplete)
        self._init_statistics_catalogs()

    # -------------------------------------------------------------------------
    # Build: Pokédex tab (NOW: internal subtabs Pokémon + Items)
    # -------------------------------------------------------------------------

    def _build_pokedex_tab(self):
        """
        Build pokedex tab.

        Build and lay out widgets for this UI section.

        Updates the UI using widget methods such as: ``addWidget``.
        """
        self.pokedex_tabs = QTabWidget()
        self.pokedex_pokemon_tab = QWidget()
        self.pokedex_items_tab = QWidget()

        self.pokedex_tabs.addTab(self.pokedex_pokemon_tab, "Pokémon")
        self.pokedex_tabs.addTab(self.pokedex_items_tab, "Items")

        layout = QVBoxLayout(self.tab_pokedex)
        layout.addWidget(self.pokedex_tabs, 1)

        self._build_pokedex_pokemon_subtab()
        self._build_pokedex_items_subtab()

    def _build_pokedex_pokemon_subtab(self):
        """
        Build pokedex pokemon subtab.

        Build and lay out widgets for this UI section.

        Updates the UI using widget methods such as: ``setEnabled``, ``addWidget``, ``addLayout``.
        """
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

        # Abilities (combo + description) - Pokémon tab
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

        # Egg groups (Pokémon tab)
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

        tab_layout = QVBoxLayout(self.pokedex_pokemon_tab)
        tab_layout.addLayout(main_row, 1)

    def _build_pokedex_items_subtab(self) -> None:
        """
        Build pokedex items subtab.

        Build and lay out widgets for this UI section. Pokédex > Items subtab:
        search (autocomplete) + show name, flavor text, and image.

        Updates the UI using widget methods such as: ``addWidget``, ``addLayout``, ``setPlaceholderText``.
        """
        root = QVBoxLayout(self.pokedex_items_tab)

        box = QGroupBox("Item Details")
        layout = QVBoxLayout(box)

        # Search
        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("Search item (type to autocomplete)")
        layout.addWidget(QLabel("Item:"))
        layout.addWidget(self.item_search)

        # Content row: image + text
        content_row = QHBoxLayout()

        self.lbl_item_image = QLabel()
        self.lbl_item_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_item_image.setFrameShape(QFrame.Shape.Panel)
        self.lbl_item_image.setFrameShadow(QFrame.Shadow.Sunken)
        self.lbl_item_image.setMinimumSize(160, 160)

        text_col = QVBoxLayout()

        self.lbl_item_name = QLabel("—")
        self.lbl_item_name.setWordWrap(True)

        self.lbl_item_desc = QLabel("—")
        self.lbl_item_desc.setWordWrap(True)
        self.lbl_item_desc.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_item_desc.setMinimumHeight(160)

        text_col.addWidget(QLabel("Name:"))
        text_col.addWidget(self.lbl_item_name)
        text_col.addSpacing(8)
        text_col.addWidget(QLabel("Description:"))
        text_col.addWidget(self.lbl_item_desc, 1)

        content_row.addWidget(self.lbl_item_image, 0)
        content_row.addLayout(text_col, 1)

        layout.addLayout(content_row, 1)
        root.addWidget(box, 1)

        # Signals
        self.item_search.returnPressed.connect(self._on_update_item_details)

        # Initial blank
        self._clear_item_details()

    # -------------------------------------------------------------------------
    # Build: Statistics tab + subtabs (Items REMOVED)
    # -------------------------------------------------------------------------

    def _build_statistics_tab(self):
        """
        Build statistics tab.

        Build and lay out widgets for this UI section.

        Updates the UI using widget methods such as: ``addWidget``.
        """
        self.stats_tabs = QTabWidget()

        self.stats_tab_general = QWidget()
        self.stats_tab_pokemon = QWidget()
        self.stats_tab_egg = QWidget()
        self.stats_tab_abilities = QWidget()

        self.stats_tabs.addTab(self.stats_tab_general, "General Statistics")
        self.stats_tabs.addTab(self.stats_tab_pokemon, "Pokemon")
        self.stats_tabs.addTab(self.stats_tab_egg, "Egg Groups")
        self.stats_tabs.addTab(self.stats_tab_abilities, "Abilities")

        # ---------------- Subtab: General Statistics ----------------
        self._build_general_statistics_subtab()

        # ---------------- Subtab: Pokemon (Histogram) ----------------
        pokemon_layout = QVBoxLayout(self.stats_tab_pokemon)
        self._build_pokemon_histogram_section(pokemon_layout)
        pokemon_layout.addStretch()

        # ---------------- Subtab: Egg Groups (CHART ONLY) ----------------
        self._build_egg_group_chart_subtab()

        # ---------------- Subtab: Abilities (description + 2 charts) ----------------
        self._build_abilities_subtab()

        # Assemble Statistics tab
        tab_layout = QVBoxLayout(self.tab_stats)
        tab_layout.addWidget(self.stats_tabs, 1)

    def _build_general_statistics_subtab(self) -> None:
        """
        Build general statistics subtab.

        Build and lay out widgets for this UI section.

        Updates the UI using widget methods such as: ``addWidget``, ``addLayout``.
        """
        # ---------------- Type Chart (filters above) ----------------
        type_box = QGroupBox("Type Chart")

        # Type chart filters
        self.chk_forms_enable = QCheckBox("Enable alternative forms")
        self.chk_forms_enable.setChecked(False)

        gens_box = QGroupBox("Generations")
        gens_layout = QGridLayout()

        self.gen_checkboxes: list[QCheckBox] = []
        for i in range(1, 10):  # 1..9
            cb = QCheckBox(f"Gen {i}")
            cb.setChecked(True)
            self.gen_checkboxes.append(cb)
            r = (i - 1) // 3
            c = (i - 1) % 3
            gens_layout.addWidget(cb, r, c)

        gens_box.setLayout(gens_layout)

        type_filters_layout = QVBoxLayout()
        type_filters_layout.addWidget(self.chk_forms_enable)
        type_filters_layout.addWidget(gens_box)

        # Type chart view
        self.type_chart_view = QChartView()
        self.type_chart_view.setRenderHint(self.type_chart_view.renderHints())

        self.lbl_type_chart_info = QLabel("—")
        self.lbl_type_chart_info.setWordWrap(True)

        type_layout = QVBoxLayout()
        type_layout.addLayout(type_filters_layout)
        type_layout.addWidget(self.type_chart_view, 1)
        type_layout.addWidget(self.lbl_type_chart_info)
        type_box.setLayout(type_layout)

        # ---------------- Generation Chart (filters above) ----------------
        gen_box = QGroupBox("Generation Chart")

        self.gen_type_filter_combo = QComboBox()

        gen_filter_row = QHBoxLayout()
        gen_filter_row.addWidget(QLabel("Type filter:"), 0)
        gen_filter_row.addWidget(self.gen_type_filter_combo, 1)

        self.gen_chart_view = QChartView()
        self.gen_chart_view.setRenderHint(self.gen_chart_view.renderHints())

        self.lbl_gen_chart_info = QLabel("—")
        self.lbl_gen_chart_info.setWordWrap(True)

        gen_layout = QVBoxLayout()
        gen_layout.addLayout(gen_filter_row)
        gen_layout.addWidget(self.gen_chart_view, 1)
        gen_layout.addWidget(self.lbl_gen_chart_info)
        gen_box.setLayout(gen_layout)

        # ---------------- Page layout: two charts side-by-side ----------------
        main_row = QHBoxLayout()
        main_row.addWidget(type_box, 1)
        main_row.addWidget(gen_box, 1)

        layout = QVBoxLayout(self.stats_tab_general)
        layout.addLayout(main_row, 1)

        # ---------------- Signals (auto-update, no buttons) ----------------
        self.chk_forms_enable.toggled.connect(self._on_update_type_chart_clicked)
        for cb in self.gen_checkboxes:
            cb.toggled.connect(self._on_update_type_chart_clicked)

        self.gen_type_filter_combo.currentIndexChanged.connect(
            self._on_update_gen_chart_clicked
        )

        # Initial render
        self._on_update_type_chart_clicked()
        self._on_update_gen_chart_clicked()

    def _build_pokemon_histogram_section(self, parent_layout: QVBoxLayout) -> None:
        """
        Build pokemon histogram section.

        Build and lay out widgets for this UI section.

        Uses the data provider API via: ``api.get_stat_histogram()``.

        Updates the UI using widget methods such as: ``addWidget``, ``addItem``.

        Parameters
        ----------
        parent_layout: Any
            Value provided by Qt (signal) or by the caller.
        """
        self.hist_group = QGroupBox("Stat Histogram (uses the top search bar)")

        hint = QLabel(
            "Type a Pokémon in the top search bar (name or number), then choose a stat and filters below."
        )
        hint.setWordWrap(True)

        # Filters (same style as General Statistics)
        self.hist_chk_forms_enable = QCheckBox("Enable alternative forms")
        self.hist_chk_forms_enable.setChecked(False)

        hist_gens_box = QGroupBox("Generations")
        hist_gens_layout = QGridLayout()
        self.hist_gen_checkboxes: list[QCheckBox] = []
        for i in range(1, 10):  # 1..9
            cb = QCheckBox(f"Gen {i}")
            cb.setChecked(True)
            self.hist_gen_checkboxes.append(cb)
            r = (i - 1) // 3
            c = (i - 1) % 3
            hist_gens_layout.addWidget(cb, r, c)
        hist_gens_box.setLayout(hist_gens_layout)

        # Controls row: stat + type filter + bins
        self.hist_stat_combo = QComboBox()
        self.hist_stat_combo.addItems(["HP", "Atk", "Def", "SpA", "SpD", "Spe"])

        self.hist_type_filter_combo = QComboBox()
        self.hist_type_filter_combo.addItem("All types", userData=None)

        self.hist_bins_combo = QComboBox()
        self.hist_bins_combo.setEditable(True)
        self.hist_bins_combo.addItems(["10", "15", "20", "25", "30", "40"])
        self.hist_bins_combo.setCurrentText("20")

        controls_row = QGridLayout()
        controls_row.addWidget(QLabel("Stat:"), 0, 0)
        controls_row.addWidget(self.hist_stat_combo, 0, 1)
        controls_row.addWidget(QLabel("Type filter:"), 1, 0)
        controls_row.addWidget(self.hist_type_filter_combo, 1, 1)
        controls_row.addWidget(QLabel("Bins:"), 2, 0)
        controls_row.addWidget(self.hist_bins_combo, 2, 1)

        controls_box = QGroupBox("Histogram Controls")
        controls_box.setLayout(controls_row)

        # Chart
        self.hist_chart_view = QChartView()

        # Info panel (left)
        self.lbl_hist_info = QLabel("—")
        self.lbl_hist_info.setWordWrap(True)

        info_box = QGroupBox("Details")
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.lbl_hist_info, 1)
        info_box.setLayout(info_layout)

        # Bottom area: left details + right chart
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(info_box, 1)  # left
        bottom_row.addWidget(self.hist_chart_view, 2)  # right (bigger)

        layout = QVBoxLayout()
        layout.addWidget(hint)
        layout.addWidget(self.hist_chk_forms_enable)
        layout.addWidget(hist_gens_box)
        layout.addWidget(controls_box)
        layout.addLayout(bottom_row, 1)

        # Save button (download chart)
        self.btn_save_hist_chart = QPushButton("Save chart…")
        layout.addWidget(self.btn_save_hist_chart, 0)

        # Signals
        self.btn_save_hist_chart.clicked.connect(self._on_save_hist_chart_clicked)

        self.hist_group.setLayout(layout)
        parent_layout.addWidget(self.hist_group)

        # Signals: auto-update (like other charts)
        self.hist_chk_forms_enable.toggled.connect(self._on_update_stat_histogram)
        for cb in self.hist_gen_checkboxes:
            cb.toggled.connect(self._on_update_stat_histogram)

        self.hist_stat_combo.currentIndexChanged.connect(self._on_update_stat_histogram)
        self.hist_type_filter_combo.currentIndexChanged.connect(
            self._on_update_stat_histogram
        )
        self.hist_bins_combo.currentTextChanged.connect(self._on_update_stat_histogram)

        # Initial render
        self._on_update_stat_histogram()

    def _build_egg_group_chart_subtab(self) -> None:
        """
        Build egg group chart subtab.

        Build and lay out widgets for this UI section.
        Egg Groups subtab: filters + uses api.get_egg_chart.

        Updates the UI using widget methods such as: ``addWidget``, ``addLayout``.
        """
        egg_box = QGroupBox("Egg Group Chart")

        egg_gens_box = QGroupBox("Generations")
        egg_gens_layout = QGridLayout()

        self.egg_gen_checkboxes: list[QCheckBox] = []
        for i in range(1, 10):  # 1..9
            cb = QCheckBox(f"Gen {i}")
            cb.setChecked(True)
            self.egg_gen_checkboxes.append(cb)
            r = (i - 1) // 3
            c = (i - 1) % 3
            egg_gens_layout.addWidget(cb, r, c)

        egg_gens_box.setLayout(egg_gens_layout)

        self.egg_type_filter_combo = QComboBox()
        egg_filter_row = QHBoxLayout()
        egg_filter_row.addWidget(QLabel("Type filter:"), 0)
        egg_filter_row.addWidget(self.egg_type_filter_combo, 1)

        self.egg_chart_view = QChartView()
        self.egg_chart_view.setRenderHint(self.egg_chart_view.renderHints())

        self.lbl_egg_chart_info = QLabel("—")
        self.lbl_egg_chart_info.setWordWrap(True)

        filters_layout = QVBoxLayout()
        filters_layout.addWidget(egg_gens_box)
        filters_layout.addLayout(egg_filter_row)

        egg_layout = QVBoxLayout()
        egg_layout.addLayout(filters_layout)
        egg_layout.addWidget(self.egg_chart_view, 1)
        egg_layout.addWidget(self.lbl_egg_chart_info)
        egg_box.setLayout(egg_layout)

        layout = QVBoxLayout(self.stats_tab_egg)
        layout.addWidget(egg_box, 1)

        # Signals: auto-update (no button)
        for cb in self.egg_gen_checkboxes:
            cb.toggled.connect(self._on_update_egg_chart_clicked)
        self.egg_type_filter_combo.currentIndexChanged.connect(
            self._on_update_egg_chart_clicked
        )

        self._on_update_egg_chart_clicked()

    def _build_abilities_subtab(self) -> None:
        """
        Build abilities subtab.

        Build and lay out widgets for this UI section.
        Abilities subtab: show description + 2 charts side-by-side.

        Updates the UI using widget methods such as: ``addWidget``, ``addLayout``, ``setPlaceholderText``.
        """
        root = QVBoxLayout(self.stats_tab_abilities)

        box = QGroupBox("Ability Details")
        layout = QVBoxLayout(box)

        # Search row
        self.ability_search = QLineEdit()
        self.ability_search.setPlaceholderText("Search ability (type to autocomplete)")
        layout.addWidget(QLabel("Ability:"))
        layout.addWidget(self.ability_search)

        # Description
        self.lbl_ability_desc_stats = QLabel("—")
        self.lbl_ability_desc_stats.setWordWrap(True)
        self.lbl_ability_desc_stats.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_ability_desc_stats.setMinimumHeight(80)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.lbl_ability_desc_stats)

        # Charts row (side-by-side)
        charts_row = QHBoxLayout()

        left_box = QGroupBox("Type Chart")
        left_layout = QVBoxLayout(left_box)
        self.ability_type_chart_view = QChartView()
        self.ability_type_chart_view.setRenderHint(
            self.ability_type_chart_view.renderHints()
        )
        self.lbl_ability_type_chart_info = QLabel("—")
        self.lbl_ability_type_chart_info.setWordWrap(True)
        left_layout.addWidget(self.ability_type_chart_view, 1)
        left_layout.addWidget(self.lbl_ability_type_chart_info)

        right_box = QGroupBox("Generation Chart")
        right_layout = QVBoxLayout(right_box)
        self.ability_gen_chart_view = QChartView()
        self.ability_gen_chart_view.setRenderHint(
            self.ability_gen_chart_view.renderHints()
        )
        self.lbl_ability_gen_chart_info = QLabel("—")
        self.lbl_ability_gen_chart_info.setWordWrap(True)
        right_layout.addWidget(self.ability_gen_chart_view, 1)
        right_layout.addWidget(self.lbl_ability_gen_chart_info)

        charts_row.addWidget(left_box, 1)
        charts_row.addWidget(right_box, 1)

        layout.addLayout(charts_row, 1)

        root.addWidget(box, 1)

        # Signals: update on Enter; completer activation hooked in _init_statistics_catalogs
        self.ability_search.returnPressed.connect(self._on_update_ability_details)

        # Initial blank
        self._clear_ability_details()

    # -------------------------------------------------------------------------
    # Charts handlers
    # -------------------------------------------------------------------------

    def _on_update_type_chart_clicked(self) -> None:
        if not hasattr(api, "get_type_chart"):
            self.lbl_type_chart_info.setText("TODO: implement api.get_type_chart(...)")
            self.type_chart_view.setChart(QChart())
            return

        forms_enable = self.chk_forms_enable.isChecked()
        generations_enable = [cb.isChecked() for cb in self.gen_checkboxes]

        try:
            chart_data = api.get_type_chart(
                language_id=self.current_language_id,
                forms_enable=forms_enable,
                generations_enable=generations_enable,
            )
            self._render_pie_chart(
                chart_view=self.type_chart_view,
                chart_data=chart_data,
                title_fallback="Type Chart",
                info_label=self.lbl_type_chart_info,
            )
        except Exception as e:
            self.lbl_type_chart_info.setText(f"Error: {e}")
            self.type_chart_view.setChart(QChart())

    def _on_update_gen_chart_clicked(self) -> None:
        if not hasattr(api, "get_gen_chart"):
            self.lbl_gen_chart_info.setText("TODO: implement api.get_gen_chart(...)")
            self.gen_chart_view.setChart(QChart())
            return

        type_filter = (
            self.gen_type_filter_combo.currentData()
            if hasattr(self, "gen_type_filter_combo")
            else None
        )

        try:
            chart_data = api.get_gen_chart(
                language_id=self.current_language_id,
                type_filter=type_filter,
            )
            self._render_pie_chart(
                chart_view=self.gen_chart_view,
                chart_data=chart_data,
                title_fallback="Generation Chart",
                info_label=self.lbl_gen_chart_info,
            )
        except Exception as e:
            self.lbl_gen_chart_info.setText(f"Error: {e}")
            self.gen_chart_view.setChart(QChart())

    def _on_update_egg_chart_clicked(self) -> None:
        if not hasattr(api, "get_egg_chart"):
            self.lbl_egg_chart_info.setText("TODO: implement api.get_egg_chart(...)")
            self.egg_chart_view.setChart(QChart())
            return

        generations_enable = [cb.isChecked() for cb in self.egg_gen_checkboxes]
        type_filter = self.egg_type_filter_combo.currentData()

        try:
            chart_data = api.get_egg_chart(
                language_id=self.current_language_id,
                type_filter=type_filter,
                generations_enable=generations_enable,
            )
            self._render_pie_chart(
                chart_view=self.egg_chart_view,
                chart_data=chart_data,
                title_fallback="Egg Group Chart",
                info_label=self.lbl_egg_chart_info,
            )
        except Exception as e:
            self.lbl_egg_chart_info.setText(f"Error: {e}")
            self.egg_chart_view.setChart(QChart())

    def _on_update_stat_histogram(self) -> None:
        if not hasattr(self, "hist_chart_view"):
            return

        if not hasattr(api, "get_stat_histogram"):
            self.lbl_hist_info.setText("TODO: implement api.get_stat_histogram(...)")
            self.hist_chart_view.setChart(QChart())
            return

        identifier = self.input_name.text().strip()  # must use top bar
        if not identifier:
            self.lbl_hist_info.setText(
                "Type a Pokémon in the top search bar to highlight it."
            )
            self.hist_chart_view.setChart(QChart())
            return

        stat_key = (
            self.hist_stat_combo.currentText().strip()
            if hasattr(self, "hist_stat_combo")
            else "HP"
        )
        type_filter = (
            self.hist_type_filter_combo.currentData()
            if hasattr(self, "hist_type_filter_combo")
            else None
        )
        forms_enable = (
            self.hist_chk_forms_enable.isChecked()
            if hasattr(self, "hist_chk_forms_enable")
            else False
        )
        generations_enable = [
            cb.isChecked() for cb in getattr(self, "hist_gen_checkboxes", [])
        ] or [True] * 9

        bins_text = (
            self.hist_bins_combo.currentText().strip()
            if hasattr(self, "hist_bins_combo")
            else "20"
        )
        try:
            bins = int(bins_text)
            if bins <= 0:
                bins = 20
        except Exception:
            bins = 20

        form = None
        if hasattr(self, "form_combo") and self.form_combo.isEnabled():
            ft = self.form_combo.currentText().strip()
            form = ft or None

        try:
            chart_data = api.get_stat_histogram(
                identifier=identifier,
                stat_key=stat_key,
                language_id=self.current_language_id,
                type_filter=type_filter,
                forms_enable=forms_enable,
                generations_enable=generations_enable,
                bins=bins,
                form=form,
            )
            self._render_histogram_chart(
                chart_view=self.hist_chart_view,
                chart_data=chart_data,
                title_fallback=f"Histogram - {stat_key}",
                info_label=self.lbl_hist_info,
            )
        except Exception as e:
            self.lbl_hist_info.setText(f"Error: {e}")
            self.hist_chart_view.setChart(QChart())

    # -------------------------------------------------------------------------
    # Abilities subtab handlers
    # -------------------------------------------------------------------------

    def _clear_ability_details(self) -> None:
        if hasattr(self, "lbl_ability_desc_stats"):
            self.lbl_ability_desc_stats.setText("—")

        if hasattr(self, "ability_type_chart_view"):
            self.ability_type_chart_view.setChart(QChart())
        if hasattr(self, "ability_gen_chart_view"):
            self.ability_gen_chart_view.setChart(QChart())

        if hasattr(self, "lbl_ability_type_chart_info"):
            self.lbl_ability_type_chart_info.setText("—")
        if hasattr(self, "lbl_ability_gen_chart_info"):
            self.lbl_ability_gen_chart_info.setText("—")

    def _on_update_ability_details(self) -> None:
        ability_text = (
            self.ability_search.text().strip()
            if hasattr(self, "ability_search")
            else ""
        )
        if not ability_text:
            self._clear_ability_details()
            return

        if not hasattr(api, "get_ability_description"):
            self.lbl_ability_desc_stats.setText(
                "Ability description API not available."
            )
        else:
            try:
                desc = api.get_ability_description(
                    ability_text,
                    False,
                    language_id=self.current_language_id,
                )
                desc_str = str(desc).replace("\n", " ").replace("\f", " ").strip()
                self.lbl_ability_desc_stats.setText(desc_str if desc_str else "—")
            except Exception as e:
                self.lbl_ability_desc_stats.setText(f"Error: {e}")

        if hasattr(api, "get_ability_type_chart"):
            try:
                cd = api.get_ability_type_chart(
                    ability_text, language_id=self.current_language_id
                )
                self._render_pie_chart(
                    chart_view=self.ability_type_chart_view,
                    chart_data=cd,
                    title_fallback="Type Chart - Ability",
                    info_label=self.lbl_ability_type_chart_info,
                )
            except Exception as e:
                self.lbl_ability_type_chart_info.setText(f"Error: {e}")
                self.ability_type_chart_view.setChart(QChart())
        else:
            self.lbl_ability_type_chart_info.setText(
                "TODO: implement api.get_ability_type_chart(...)"
            )
            self.ability_type_chart_view.setChart(QChart())

        if hasattr(api, "get_ability_gen_chart"):
            try:
                cd = api.get_ability_gen_chart(
                    ability_text, language_id=self.current_language_id
                )
                self._render_pie_chart(
                    chart_view=self.ability_gen_chart_view,
                    chart_data=cd,
                    title_fallback="Generation Chart - Ability",
                    info_label=self.lbl_ability_gen_chart_info,
                )
            except Exception as e:
                self.lbl_ability_gen_chart_info.setText(f"Error: {e}")
                self.ability_gen_chart_view.setChart(QChart())
        else:
            self.lbl_ability_gen_chart_info.setText(
                "TODO: implement api.get_ability_gen_chart(...)"
            )
            self.ability_gen_chart_view.setChart(QChart())

    # -------------------------------------------------------------------------
    # Items (NOW: Pokédex > Items)
    # -------------------------------------------------------------------------

    def _clear_item_details(self) -> None:
        if hasattr(self, "lbl_item_name"):
            self.lbl_item_name.setText("—")
        if hasattr(self, "lbl_item_desc"):
            self.lbl_item_desc.setText("—")
        if hasattr(self, "lbl_item_image"):
            self.lbl_item_image.setPixmap(QPixmap())
            self.lbl_item_image.setText("—")

    def _on_update_item_details(self) -> None:
        item_text = (
            self.item_search.text().strip() if hasattr(self, "item_search") else ""
        )
        if not item_text:
            self._clear_item_details()
            return

        if not hasattr(api, "get_item"):
            self._clear_item_details()
            if hasattr(self, "lbl_item_desc"):
                self.lbl_item_desc.setText("Item flavor text API not available.")
            return

        try:
            res = api.get_item(item_text, language_id=self.current_language_id)
            name = str(res.get("name", "—"))
            desc = (
                str(res.get("item_flavor_text", "—"))
                .replace("\n", " ")
                .replace("\f", " ")
                .strip()
            )
            image = res.get("image")

            self.lbl_item_name.setText(f"<b>{name}</b>")
            self.lbl_item_desc.setText(desc if desc else "—")

            pm = _load_pixmap(str(image), QSize(160, 160)) if image else QPixmap()
            if pm.isNull():
                self.lbl_item_image.setPixmap(QPixmap())
                self.lbl_item_image.setText("No image")
            else:
                self.lbl_item_image.setPixmap(pm)
                self.lbl_item_image.setText("")
        except Exception as e:
            self._clear_item_details()
            self.lbl_item_desc.setText(f"Error: {e}")

    # -------------------------------------------------------------------------
    # Pie renderer (includes readability tweaks for few slices)
    # -------------------------------------------------------------------------

    def _render_pie_chart(
        self,
        chart_view: QChartView,
        chart_data,
        title_fallback: str,
        info_label: QLabel,
    ) -> None:
        series = QPieSeries()

        labels = getattr(chart_data, "labels", []) or []
        values = getattr(chart_data, "values", []) or []

        for label, value in zip(labels, values):
            try:
                v = float(value)
            except Exception:
                continue
            if v <= 0:
                continue

            slice_ = series.append(str(label), v)

            count = int(v) if float(v).is_integer() else v
            slice_.setLabel(f"{label} {count}")
            slice_.setLabelVisible(True)

            slice_.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
            slice_.setLabelArmLengthFactor(0.15)

        slices = series.slices()
        n_slices = len(slices)

        if n_slices <= 6:
            for s in slices:
                s.setExploded(False)
                s.setLabelArmLengthFactor(0.0)
                if hasattr(QPieSlice.LabelPosition, "LabelInsideNormal"):
                    s.setLabelPosition(QPieSlice.LabelPosition.LabelInsideNormal)
                else:
                    s.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)

            if hasattr(series, "setPieSize"):
                series.setPieSize(0.85)
            show_legend = False
        else:
            if hasattr(series, "setPieSize"):
                series.setPieSize(0.65)

            right = []
            left = []
            for s in slices:
                if not (hasattr(s, "startAngle") and hasattr(s, "angleSpan")):
                    continue

                mid = float(s.startAngle()) + float(s.angleSpan()) / 2.0
                rad = math.radians(mid)
                side_is_right = math.cos(rad) >= 0
                y = math.sin(rad)
                (right if side_is_right else left).append((y, s))

            for side_list in (right, left):
                side_list.sort(key=lambda t: t[0], reverse=True)
                k = 0
                for _, s in side_list:
                    pct = float(s.percentage()) if hasattr(s, "percentage") else 0.0
                    if pct < 0.06:
                        s.setLabelArmLengthFactor(0.15 + 0.03 * k)
                        k += 1
                    else:
                        s.setLabelArmLengthFactor(0.15)

                    if pct < 0.03 and hasattr(s, "setExploded"):
                        s.setExploded(True)
                        if hasattr(s, "setExplodeDistanceFactor"):
                            s.setExplodeDistanceFactor(0.06)

            show_legend = False

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(str(getattr(chart_data, "title", title_fallback)))
        chart.legend().setVisible(show_legend)
        chart.setMargins(QMargins(20, 10, 20, 20))

        chart_view.setChart(chart)

        total = getattr(chart_data, "total", None)
        meta = getattr(chart_data, "meta", {}) or {}
        meta_text = (
            ", ".join([f"{k}={v}" for k, v in meta.items()])
            if isinstance(meta, dict)
            else str(meta)
        )

        if total is not None:
            info_label.setText(f"Total Pokémon counted: {total}\n{meta_text}")
        else:
            info_label.setText(meta_text or "—")

    def _render_histogram_chart(
        self,
        chart_view: QChartView,
        chart_data,
        title_fallback: str,
        info_label: QLabel,
    ) -> None:
        labels = getattr(chart_data, "labels", []) or []
        values = getattr(chart_data, "values", []) or []
        total = getattr(chart_data, "total", None)
        meta = getattr(chart_data, "meta", {}) or {}

        series = QBarSeries()

        base_set = QBarSet("Count")
        for v in values:
            try:
                base_set.append(int(v))
            except Exception:
                base_set.append(0)
        series.append(base_set)

        selected_idx = None
        try:
            raw = meta.get("selected_bin_index") if isinstance(meta, dict) else None
            if raw is not None and str(raw) != "None":
                selected_idx = int(raw)
        except Exception:
            selected_idx = None

        if selected_idx is not None and 0 <= selected_idx < len(values):
            sel_set = QBarSet("Selected")
            for i, v in enumerate(values):
                sel_set.append(int(v) if i == selected_idx else 0)
            series.append(sel_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(str(getattr(chart_data, "title", title_fallback)))

        axis_x = QBarCategoryAxis()
        axis_x.append([str(x) for x in labels])
        axis_x.setLabelsAngle(-60)

        axis_y = QValueAxis()
        axis_y.setMin(0)
        try:
            ymax = max([int(x) for x in values]) if values else 1
        except Exception:
            ymax = 1
        axis_y.setMax(max(1, int(ymax * 1.15)))

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)

        chart.legend().setVisible(selected_idx is not None)
        chart_view.setChart(chart)

        # ---- Info text (only the fields you asked for) ----
        desc = ""
        stat_key = ""
        bins = ""
        selected_identifier = ""
        selected_value = ""
        selected_rank = ""
        rank_total = ""

        if isinstance(meta, dict):
            desc = str(meta.get("description", "")).strip()
            stat_key = str(meta.get("stat_key", "")).strip()
            bins = str(meta.get("bins", "")).strip()
            selected_identifier = str(meta.get("selected_identifier", "")).strip()
            selected_value = str(meta.get("selected_value", "")).strip()
            selected_rank = str(meta.get("selected_rank", "")).strip()
            rank_total = str(meta.get("rank_total", "")).strip()

        if not stat_key:
            stat_key = title_fallback.replace("Histogram -", "").strip() or "—"

        # Resolve selected Pokémon name + dex number (Pokédex #)
        selected_name = "—"
        selected_dex = "—"

        # Prefer current loaded Pokémon if it matches the input bar
        try:
            cur_text = self.input_name.text().strip()
            if (
                isinstance(self.current_data, dict)
                and self.current_data
                and cur_text
                and selected_identifier
                and cur_text.casefold() == selected_identifier.casefold()
            ):
                selected_name = str(self.current_data.get("name", "—"))
                selected_dex = str(self.current_data.get("dex_number", "—"))
        except Exception:
            pass

        if selected_name == "—" or selected_dex == "—":
            # Try API directly (identifier might be name or dex number)
            if selected_identifier:
                try:
                    p = api.get_pokemon(
                        selected_identifier,
                        form=(self.form_combo.currentText().strip() or None)
                        if hasattr(self, "form_combo") and self.form_combo.isEnabled()
                        else None,
                        language_id=self.current_language_id,
                    )
                    if isinstance(p, dict):
                        selected_name = str(p.get("name", selected_name))
                        selected_dex = str(p.get("dex_number", selected_dex))
                except Exception:
                    # Fallback: if the user typed a localized name, map to species id then fetch
                    try:
                        lang = int(self.current_language_id)
                        row = pokemon_species_names_df[
                            (pokemon_species_names_df["local_language_id"] == lang)
                            & (
                                pokemon_species_names_df["name"]
                                .astype(str)
                                .str.casefold()
                                == selected_identifier.casefold()
                            )
                        ]
                        if not row.empty:
                            dex_num = int(row["pokemon_species_id"].iloc[0])
                            p = api.get_pokemon(
                                dex_num,
                                form=(self.form_combo.currentText().strip() or None)
                                if hasattr(self, "form_combo")
                                and self.form_combo.isEnabled()
                                else None,
                                language_id=self.current_language_id,
                            )
                            if isinstance(p, dict):
                                selected_name = str(p.get("name", selected_name))
                                selected_dex = str(p.get("dex_number", selected_dex))
                    except Exception:
                        pass

        lines: list[str] = []
        if total is not None:
            lines.append(f"Total Pokémon counted: {total}")
        if desc:
            lines.append(f"Description: {desc}")
        lines.append(f"Stat: {stat_key}")
        if bins:
            lines.append(f"Bins: {bins}")
        else:
            lines.append(f"Bins: {len(labels)}")

        lines.append(f"Selected Pokémon: {selected_name}")
        lines.append(f"Dex #: {selected_dex}")

        if selected_value and selected_value != "None":
            lines.append(f"{stat_key} value: {selected_value}")
        else:
            lines.append(f"{stat_key} value: —")

        # Rank
        if selected_rank and selected_rank != "None":
            rt = (
                rank_total
                if (rank_total and rank_total != "None")
                else (str(total) if total is not None else "—")
            )
            lines.append(f"Rank (within filters): {selected_rank} of {rt}")
        else:
            lines.append("Rank (within filters): —")

        info_label.setText("\n".join(lines))

    def _on_save_hist_chart_clicked(self) -> None:
        """Save the current histogram chart as an image file (PNG/JPG)."""
        if not hasattr(self, "hist_chart_view"):
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save histogram chart",
            "histogram.png",
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)",
        )
        if not filename:
            return

        pixmap = self.hist_chart_view.grab()
        pixmap.save(filename)

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

        self._init_pokemon_autocomplete()
        self._init_statistics_catalogs()

        if hasattr(self, "type_chart_view"):
            self._on_update_type_chart_clicked()
        if hasattr(self, "gen_chart_view"):
            self._on_update_gen_chart_clicked()
        if hasattr(self, "egg_chart_view"):
            self._on_update_egg_chart_clicked()

        if hasattr(self, "ability_search") and self.ability_search.text().strip():
            self._on_update_ability_details()

        if hasattr(self, "item_search") and self.item_search.text().strip():
            self._on_update_item_details()

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
        return self._get_all_names()

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

    def _get_all_names(
        self,
        names_df=pokemon_species_names_df,
        base_df=pokemon_species_df,
        lang_col="local_language_id",
        name_col="name",
        base_identifier_col="identifier",
    ) -> list[str]:
        lang = self.current_language_id
        df = names_df[names_df[lang_col] == lang]
        if df.empty:
            return (
                base_df[base_identifier_col]
                .astype(str)
                .str.replace("-", "", regex=False)
                .str.capitalize()
                .tolist()
            )
        return df[name_col].tolist()

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

            self._bind_abilities(
                data.get("abilities") or [],
                data.get("is_hidden_ability") or [],
            )
            self._bind_egg_groups(data.get("egg_groups") or [])

            cries = data.get("cries") or []
            self.btn_play_cry.setEnabled(bool(cries))
            self.current_cry_index = 0

            if hasattr(self, "hist_chart_view"):
                self._on_update_stat_histogram()

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

    # ----------------- Evolution display (tree) + click-to-view + item click-to-items -----------------

    def _go_to_pokemon(self, identifier: str | int) -> None:
        ident = str(identifier).strip()
        if not ident:
            return
        self.input_name.setText(ident)
        self.current_identifier = ident
        self._load_pokemon_data(identifier=ident, form=None)

    def _go_to_item_by_name(self, item_name: str) -> None:
        name = str(item_name).strip()
        if not name:
            return
        # go to main Pokédex tab, then its Items subtab
        self.tabs.setCurrentWidget(self.tab_pokedex)
        if hasattr(self, "pokedex_tabs"):
            self.pokedex_tabs.setCurrentWidget(self.pokedex_items_tab)

        if hasattr(self, "item_search"):
            self.item_search.setText(name)
            self._on_update_item_details()

    def _resolve_item_name_from_sprite(self, item_sprite_path: str) -> str | None:
        try:
            if not item_sprite_path:
                return None

            ident = Path(str(item_sprite_path)).stem  # e.g. "thunder-stone"
            if not ident:
                return None

            row = items_df[items_df["identifier"].astype(str) == ident]
            if row.empty:
                return None
            item_id = int(row.iloc[0]["id"])

            name_row = item_names_df[
                (item_names_df["item_id"] == item_id)
                & (item_names_df["local_language_id"] == int(self.current_language_id))
            ]
            if not name_row.empty:
                return str(name_row.iloc[0]["name"])

            name_row = item_names_df[
                (item_names_df["item_id"] == item_id)
                & (item_names_df["local_language_id"] == 9)
            ]
            if not name_row.empty:
                return str(name_row.iloc[0]["name"])

            return None
        except Exception:
            return None

    def _bind_evolution_line(self, evo_data):
        while self.evo_row.count() > 0:
            item = self.evo_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not evo_data:
            self.evo_row.addWidget(QLabel("—"))
            self.evo_row.addStretch()
            return

        # Legacy support: list[dict] (old API)
        if isinstance(evo_data, list):
            for node in evo_data:
                w = self._make_evo_pokemon_card(
                    name=str(node.get("name", "?")),
                    image=str(node.get("image", "")) if node.get("image") else None,
                    dex_no=node.get("dex_number", None),
                )
                self.evo_row.addWidget(w)
            self.evo_row.addStretch()
            return

        # New API: PokemonEvolNode-like object
        root_widget = self._make_evo_subtree_widget(evo_data)
        self.evo_row.addWidget(root_widget)
        self.evo_row.addStretch()

    def _make_evo_pokemon_card(
        self, name: str, image: str | None, dex_no: int | None
    ) -> QWidget:
        cont = QWidget()
        box = QVBoxLayout(cont)
        box.setContentsMargins(6, 6, 6, 6)
        box.setSpacing(6)

        btn_img = QToolButton()
        btn_img.setAutoRaise(True)
        btn_img.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_img.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn_img.setIconSize(QSize(96, 96))

        pm = _load_pixmap(image, QSize(96, 96)) if image else QPixmap()
        if pm.isNull():
            btn_img.setText("—")
        else:
            btn_img.setIcon(QIcon(pm))

        if dex_no is not None:
            btn_img.clicked.connect(
                lambda _=False, d=int(dex_no): self._go_to_pokemon(d)
            )
        else:
            btn_img.clicked.connect(lambda _=False, n=name: self._go_to_pokemon(n))

        lbl_name = QLabel(name, alignment=Qt.AlignmentFlag.AlignCenter)
        lbl_name.setWordWrap(True)

        lbl_dex = QLabel(
            f"Dex #: {dex_no}" if dex_no is not None else "Dex #: —",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        box.addWidget(btn_img, alignment=Qt.AlignmentFlag.AlignCenter)
        box.addWidget(lbl_name)
        box.addWidget(lbl_dex)

        cont.setMinimumWidth(130)
        return cont

    def _make_evo_transition_widget(
        self,
        trigger_value: str | None,
        item_image: str | None,
    ) -> QWidget:
        cont = QWidget()
        box = QVBoxLayout(cont)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)

        lbl_arrow = QLabel("<b>→</b>", alignment=Qt.AlignmentFlag.AlignCenter)

        tv = (trigger_value or "").strip()
        show_item = bool(item_image) and str(item_image) != "NaN"

        # Clickable item icon (when exists) => go to Pokédex > Items with item selected
        item_btn: QToolButton | None = None
        if show_item:
            item_btn = QToolButton()
            item_btn.setAutoRaise(True)
            item_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            item_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            item_btn.setIconSize(QSize(36, 36))

            pm = _load_pixmap(str(item_image), QSize(36, 36))
            if not pm.isNull():
                item_btn.setIcon(QIcon(pm))
            else:
                item_btn.setText("—")

            # Trigger_value may include conditions.
            resolved_item_name = (
                self._resolve_item_name_from_sprite(str(item_image))
                if show_item
                else None
            )

            # Fallback: try to extract an item name from the trigger text (e.g., "Held: Oval Stone")
            fallback_item_name = None
            if not resolved_item_name and tv and tv != "NaN":
                # common patterns: "Held: X" or plain "X"
                # keep it conservative: only take the part after "Held:" if present
                if "held:" in tv.casefold():
                    fallback_item_name = tv.split(":", 1)[-1].strip()
                else:
                    fallback_item_name = tv.strip()

            item_name = resolved_item_name or fallback_item_name

            if item_name:
                item_btn.clicked.connect(
                    lambda _=False, n=str(item_name): self._go_to_item_by_name(n)
                )
            else:
                # still switch to items tab, but without reliable prefill
                item_btn.clicked.connect(lambda _=False: self._go_to_item_by_name(""))

        lbl_value = QLabel(tv if tv else "—", alignment=Qt.AlignmentFlag.AlignCenter)
        lbl_value.setWordWrap(True)
        lbl_value.setMaximumWidth(140)

        box.addWidget(lbl_arrow)
        if item_btn is not None:
            box.addWidget(item_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        box.addWidget(lbl_value)

        return cont

    def _make_evo_subtree_widget(self, node) -> QWidget:
        dex_no = int(getattr(node, "dex_no", 0))
        name = str(getattr(node, "name", "?"))
        image = (
            str(getattr(node, "image", "")) if getattr(node, "image", None) else None
        )

        children = getattr(node, "evolutions", ()) or ()
        children = tuple(children)

        if len(children) == 0:
            return self._make_evo_pokemon_card(name=name, image=image, dex_no=dex_no)

        if len(children) == 1:
            child = children[0]
            child_trigger_value = str(getattr(child, "evol_trigger_value", "NaN"))
            child_item_image = str(getattr(child, "evol_image", "NaN"))

            cont = QWidget()
            row = QHBoxLayout(cont)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)

            row.addWidget(
                self._make_evo_pokemon_card(name=name, image=image, dex_no=dex_no)
            )
            row.addWidget(
                self._make_evo_transition_widget(child_trigger_value, child_item_image)
            )
            row.addWidget(self._make_evo_subtree_widget(child))

            return cont

        cont = QWidget()
        grid = QGridLayout(cont)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        root_card = self._make_evo_pokemon_card(name=name, image=image, dex_no=dex_no)
        grid.addWidget(
            root_card, 0, 0, len(children), 1, alignment=Qt.AlignmentFlag.AlignTop
        )

        for i, child in enumerate(children):
            child_trigger_value = str(getattr(child, "evol_trigger_value", "NaN"))
            child_item_image = str(getattr(child, "evol_image", "NaN"))

            grid.addWidget(
                self._make_evo_transition_widget(child_trigger_value, child_item_image),
                i,
                1,
                alignment=Qt.AlignmentFlag.AlignTop,
            )
            grid.addWidget(
                self._make_evo_subtree_widget(child),
                i,
                2,
                alignment=Qt.AlignmentFlag.AlignTop,
            )

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

    # -------- Abilities (Pokémon tab) --------

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
            name: str = str(name_raw)
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

        if isinstance(data, tuple) and len(data) == 2:
            ability_name, is_hidden = data
            ability_str = str(ability_name).strip()
            is_hidden_bool = bool(is_hidden)
        else:
            ability_str = str(self.ability_combo.currentText()).strip()
            is_hidden_bool = False

        if not ability_str:
            self.lbl_ability_desc.setText("—")
            return

        if not hasattr(api, "get_ability_description"):
            self.lbl_ability_desc.setText("Ability description API not available.")
            return

        try:
            desc = api.get_ability_description(
                ability_str, is_hidden_bool, language_id=self.current_language_id
            )
            desc_str = str(desc).replace("\n", " ").replace("\f", " ").strip()
            self.lbl_ability_desc.setText(desc_str if desc_str else "—")
        except Exception as e:
            self.lbl_ability_desc.setText(f"Error: {e}")

    # -------- Egg groups (Pokémon tab) --------

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
            resolved = _resolve_asset_path(url_or_path)
            if resolved.startswith(("http://", "https://")):
                self.player.setSource(QUrl(resolved))
            else:
                self.player.setSource(QUrl.fromLocalFile(os.path.abspath(resolved)))
            self.audio.setVolume(0.8)
            self.player.play()
        except Exception as e:
            QMessageBox.warning(self, "Audio", f"Could not play cry:\n{e}")

    # -------------------------------------------------------------------------
    # Statistics catalogs + autocompletes (Items completer now targets Pokédex > Items)
    # -------------------------------------------------------------------------

    def _init_statistics_catalogs(self):
        if hasattr(self, "gen_type_filter_combo"):
            self._fill_chart_type_filter_combo(self.gen_type_filter_combo)

        if hasattr(self, "egg_type_filter_combo"):
            self._fill_chart_type_filter_combo(self.egg_type_filter_combo)

        if hasattr(self, "hist_type_filter_combo"):
            self._fill_chart_type_filter_combo(self.hist_type_filter_combo)
            self._on_update_stat_histogram()

        ability_names = self._fetch_catalog_strings("get_all_abilities")
        self._ability_model = QStringListModel(
            sorted(set(ability_names), key=str.casefold), self
        )
        self._ability_completer = QCompleter(self._ability_model, self)
        self._ability_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._ability_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )

        if hasattr(self, "ability_search"):
            self.ability_search.setCompleter(self._ability_completer)
            try:
                self._ability_completer.activated.connect(
                    lambda _=None: self._on_update_ability_details()
                )
            except Exception:
                pass

        item_names = self._fetch_catalog_strings("get_all_items")
        self._item_model = QStringListModel(
            sorted(set(item_names), key=str.casefold), self
        )
        self._item_completer = QCompleter(self._item_model, self)
        self._item_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._item_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )

        if hasattr(self, "item_search"):
            self.item_search.setCompleter(self._item_completer)
            try:
                self._item_completer.activated.connect(
                    lambda _=None: self._on_update_item_details()
                )
            except Exception:
                pass

        if hasattr(self, "gen_type_filter_combo"):
            self._on_update_gen_chart_clicked()
        if hasattr(self, "egg_type_filter_combo"):
            self._on_update_egg_chart_clicked()

    def _fetch_catalog_strings(self, api_method_name: str) -> list[str]:
        if not hasattr(api, api_method_name):
            return []

        try:
            method = getattr(api, api_method_name)
            items = method(language_id=self.current_language_id)
        except Exception:
            return []

        out: list[str] = []
        for it in items or []:
            if isinstance(it, list | tuple) and len(it) >= 2:
                out.append(str(it[1]))
            else:
                out.append(str(it))
        return out

    def _fill_chart_type_filter_combo(self, combo: QComboBox) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All types", userData=None)

        added_any = False
        if hasattr(api, "get_all_types"):
            try:
                items = api.get_all_types(language_id=self.current_language_id) or []
                for it in items:
                    if isinstance(it, list | tuple) and len(it) >= 2:
                        raw_key = str(it[0]).strip()
                        label = str(it[1]).strip()
                    else:
                        raw_key = str(it).strip()
                        label = raw_key

                    identifier: str | None = None

                    if raw_key.isdigit():
                        tid = int(raw_key)
                        if 1 <= tid <= len(TYPE_IDENTIFIERS):
                            identifier = TYPE_IDENTIFIERS[tid - 1]
                    else:
                        identifier = raw_key.lower()

                    if identifier:
                        combo.addItem(label, userData=identifier)
                        added_any = True
            except Exception:
                added_any = False

        if not added_any:
            for ident in TYPE_IDENTIFIERS:
                combo.addItem(ident.capitalize(), userData=ident)

        combo.blockSignals(False)


# ---- Entrypoint ---------------------------------------------------------------


def run():
    """
    Run.

    Application entrypoint: create the Qt app and start the event loop.
    """
    app = QApplication(sys.argv)
    w = PokedexWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    run()
