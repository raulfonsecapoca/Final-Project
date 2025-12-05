"""
Pokedex page using PySide6.

This file expects pokedex.my_module.typed_function to expose:
- get_pokemon(identifier: str, form: str | None = None, language_id: int = 9) -> dict
  returning keys: name, dex_number, image, cries (list[str]), types (list[str]),
  base_stats (dict[str,int]), evolution_line (list[dict{name,image}]), forms (list[str]|optional)
- (optional) get_available_forms(identifier) -> list[str]
- (optional) get_pokedex_flavor(identifier: str, language_id: int = 9)
  returning {"versions": list, "flavor_texts": list}
"""

import sys
import os
from typing import List, Tuple
from pathlib import Path

import requests
import pandas as pd
from PySide6.QtCore import Qt, QSize, QUrl, QStringListModel
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCompleter,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLineEdit,
    QScrollArea,
    QFrame,
    QMessageBox,
    QComboBox,
    QSizePolicy,
    QGroupBox,
    QToolButton,
)

from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from pokedex.my_module import typed_function as api  # your data provider

# ---- CSVs for language metadata (used only for the language buttons) ---------
language_names_df = pd.read_csv("data/csv/language_names.csv")
languages_df = pd.read_csv("data/csv/languages.csv")
pokemon_species_df = pd.read_csv("data/csv/pokemon_species.csv")
pokemon_species_names_df = pd.read_csv("data/csv/pokemon_species_names.csv") # for localized names

BASE_DIR = Path(__file__).resolve().parent.parent  # Final-Project/
TYPE_ICON_DIR = BASE_DIR / "data" / "sprites" / "sprites" / "types" / "generation-ix" / "scarlet-violet"



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
        self.setMinimumSize(900, 650)
        self.setWindowIcon(QIcon("data/sprites/sprites/items/poke-ball.png"))

        # Playback
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)

        # ---------- Top bar: search + form combo + cry ----------
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Enter Pokémon name or number (e.g., pikachu or 25)")
        self.btn_load = QPushButton("Load")
        self.btn_play_cry = QPushButton("Play Cry")
        self.btn_play_cry.setEnabled(False)

        self.form_combo = QComboBox()
        self.form_combo.setEnabled(False)
        self.form_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.form_combo.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.form_combo.setMinimumContentsLength(12)

        # Forms combo state (frozen order)
        self._forms_cache_identifier = None
        self._forms_cache_list: List[str] = None  # type: ignore
        self._forms_order: List[str] = []

        # ---------- Language bar (11 official languages) ----------
        # Default language is English (id=9)
        self.current_language_id = 9

        # Build official languages dynamically from languages.csv (official==1), ordered.
        official_ids: List[int] = (
            languages_df[languages_df["official"] == 1]
            .sort_values("order")["id"]
            .astype(int)
            .tolist()
        )
        # Create (id, display_name) pairs using autonyms
        self._official_langs: List[Tuple[int, str]] = [(lid, _lang_autonym(lid)) for lid in official_ids]

        # ---------- Left column ----------
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

        # Pokédex flavor (versions + text)
        self.dex_group = QGroupBox("Pokédex Entry")
        self.dex_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.dex_combo = QComboBox()
        self.dex_combo.setEnabled(False)
        self.dex_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.dex_combo.currentIndexChanged.connect(self._on_pokedex_version_changed)

        self.lbl_flavor = QLabel("—")
        self.lbl_flavor.setWordWrap(True)
        self.lbl_flavor.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_flavor.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self.lbl_flavor.setMinimumHeight(140)

        dex_layout = QVBoxLayout()
        row = QHBoxLayout()
        row.addWidget(QLabel("Version:"))
        row.addWidget(self.dex_combo, 1)
        dex_layout.addLayout(row)
        dex_layout.addWidget(self.lbl_flavor)
        self.dex_group.setLayout(dex_layout)
        self.dex_group.setEnabled(False)

        # ---------- Right column ----------
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

        # ---------- Layout assembly ----------
        top_row = QHBoxLayout()
        top_row.addWidget(self.input_name, 3)
        top_row.addWidget(self.btn_load, 0)
        top_row.addSpacing(12)
        top_row.addWidget(QLabel("Form:"), 0)
        top_row.addWidget(self.form_combo, 0)
        top_row.addSpacing(12)
        top_row.addWidget(self.btn_play_cry, 0)

        # Language bar
        self.lang_row = QHBoxLayout()
        self._build_language_bar(self.lang_row)

        left_col = QVBoxLayout()
        left_col.addWidget(self.lbl_sprite)
        left_col.addSpacing(8)
        left_col.addWidget(self.lbl_name)
        left_col.addWidget(self.lbl_dex)
        left_col.addLayout(self.types_row)
        left_col.addSpacing(8)
        left_col.addWidget(self.dex_group)
        left_col.addStretch()

        right_col = QVBoxLayout()
        right_col.addWidget(stats_group)
        right_col.addWidget(evo_group, 1)

        main_row = QHBoxLayout()
        main_row.addLayout(left_col, 1)
        main_row.addLayout(right_col, 2)

        root = QVBoxLayout(self)
        root.addLayout(top_row)
        root.addLayout(self.lang_row)  # language buttons under the top bar
        root.addSpacing(6)
        root.addLayout(main_row, 1)

        # ---------- Signals ----------
        self.btn_load.clicked.connect(self._on_load_clicked)
        self.btn_play_cry.clicked.connect(self._on_play_cry_clicked)
        self.form_combo.currentTextChanged.connect(self._on_form_changed)

        # State
        self.current_identifier = None
        self.current_data = {}
        self.current_cry_index = 0

        # Pokédex flavor state
        self._flavor_versions: List[str] = []
        self._flavor_texts: List[str] = []

        # Self autocomplete of the searching bar
        self._init_autocomplete()


    # ---- Language bar ---------------------------------------------------------

    def _build_language_bar(self, layout: QHBoxLayout):
        """Create the official language buttons (autonyms)."""
        layout.addWidget(QLabel("Language:"))
        self._lang_buttons: List[QToolButton] = []

        for lang_id, display in self._official_langs:
            btn = QToolButton()
            btn.setText(display)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)  # radio-like behavior
            if lang_id == self.current_language_id:
                btn.setChecked(True)
            btn.clicked.connect(lambda _=False, lid=lang_id: self._on_language_selected(lid))
            self._lang_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

    def _on_language_selected(self, lang_id: int):
        """Set language and reload current Pokémon."""
        if self.current_language_id == lang_id:
            return
        self.current_language_id = lang_id

        if self.current_identifier:
            current_form = self.form_combo.currentText().strip() or None if self.form_combo.count() > 0 else None
            self._load_pokemon_data(identifier=self.current_identifier, form=current_form)

    # -------------------- Data loading and UI binding --------------------------

    def _on_load_clicked(self):
        ident = self.input_name.text().strip()
        if not ident:
            QMessageBox.warning(self, "Pokédex", "Please type a Pokémon name or number.")
            return
        self.current_identifier = ident
        self._load_pokemon_data(identifier=ident, form=None)

    def _on_form_changed(self, form_text: str):
        if not self.current_identifier:
            return
        self._load_pokemon_data(identifier=self.current_identifier, form=(form_text or None))

    def _load_pokemon_data(self, identifier: str, form: str | None):
        """Call API and bind to UI; always pass current language_id."""
        try:
            if hasattr(api, "get_pokemon"):
                data = api.get_pokemon(identifier, form=form, language_id=self.current_language_id)
            else:
                data = api(identifier)  # type: ignore

            if not isinstance(data, dict):
                raise ValueError("typed_function.get_pokemon must return a dict")

            self.current_data = data
            self._bind_header(data)
            self._bind_types(data.get("types", []))
            self._bind_stats(data.get("base_stats", {}))
            self._bind_evolution_line(data.get("evolution_line", []))
            self._bind_forms(identifier, data)
            self._bind_pokedex_flavor(identifier)  # uses current language id

            cries = data.get("cries") or []
            self.btn_play_cry.setEnabled(bool(cries))
            self.current_cry_index = 0

        except Exception as e:
            QMessageBox.critical(self, "Error loading Pokémon", str(e))
            
    # ---- Binders --------------------------------------------------------------

    def _bind_header(self, data: dict):
        name = data.get("name", "Unknown")
        dex = data.get("dex_number", "—")
        self.lbl_name.setText(f"<b>{name}</b>")
        self.lbl_dex.setText(f"Dex #: {dex}")

        image = data.get("image")
        pm = _load_pixmap(image) if image else QPixmap()
        if pm.isNull():
            self.lbl_sprite.setText("No image")
        else:
            self.lbl_sprite.setPixmap(pm)
            self.lbl_sprite.setText("")

    def _bind_types(self, types: list):
        """Mostrar los tipos como iconos, usando los ids que vienen en 'types'."""
        # limpiar layout    
        while self.types_row.count() > 0:
            item = self.types_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self.types_row.addStretch()

        for t in types:
            # t debería ser un número de tipo (por ejemplo 10)
            try:
                type_id = int(t)
            except (TypeError, ValueError):
            # si viene algo raro, lo mostramos como texto
                lbl = QLabel(str(t))
                self.types_row.addWidget(lbl)
                continue

            icon_path = TYPE_ICON_DIR / f"{type_id}.png"

            lbl = QLabel()
            pm = QPixmap(str(icon_path))
            if pm.isNull():
                # si no se pudo cargar la imagen, mostramos el id como texto
                lbl.setText(str(type_id))
            else:
                lbl.setPixmap(pm)

            self.types_row.addWidget(lbl)

        self.types_row.addStretch()


    def _bind_stats(self, stats: dict):
        for key, lbl in self.stats_labels.items():
            val = stats.get(key) or stats.get(key.lower()) or "—"
            lbl.setText(str(val))

    def _bind_evolution_line(self, evo_list: List[dict]):
        """Render evolution cards horizontally inside a scroll area."""
        while self.evo_row.count() > 0:
            item = self.evo_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for node in evo_list:
            # NEW: also pass dex_number to the card
            w = self._make_evo_card(
                name=node.get("name", "?"),
                image=node.get("image"),
                dex_number=node.get("dex_number")
            )
            self.evo_row.addWidget(w)
        self.evo_row.addStretch()


    def _make_evo_card(self, name: str, image: str | None, dex_number: int | None) -> QWidget:
        """Create a small card with sprite, name, dex number and a button to open that Pokémon by dex number."""
        box = QVBoxLayout()
        img = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        pm = _load_pixmap(image, QSize(96, 96)) if image else QPixmap()
        img.setPixmap(pm) if not pm.isNull() else img.setText("—")

        nm = QLabel(name, alignment=Qt.AlignmentFlag.AlignCenter)
        nm.setWordWrap(True)

        # NEW: show Dex number
        dx = QLabel(f"Dex #: {dex_number}" if dex_number is not None else "Dex #: —",
                    alignment=Qt.AlignmentFlag.AlignCenter)

        btn = QPushButton("View")
        # NEW: load by dex number (fallback to name if missing)
        if dex_number is not None:
            btn.clicked.connect(lambda: self._load_pokemon_data(identifier=str(dex_number), form=None))
        else:
            btn.clicked.connect(lambda: self._load_pokemon_data(identifier=name, form=None))

        cont = QWidget()
        box.addWidget(img)
        box.addWidget(nm)
        box.addWidget(dx)  # NEW: add dex label to the card
        box.addWidget(btn)
        cont.setLayout(box)
        cont.setMinimumWidth(120)
        return cont


    # -------- Forms combo: keep stable order (frozen) --------
    def _bind_forms(self, identifier: str, data: dict):
        """Populate the forms combo box while keeping the ORIGINAL order stable."""

        # If the species changed, reset the frozen order
        if self._forms_cache_identifier != identifier:
            self._forms_order = []

        # Get the full list of forms
        forms = data.get("forms")
        if forms is None and hasattr(api, "get_available_forms"):
            try:
                forms = api.get_available_forms(identifier)
            except Exception:
                forms = None

        # Normalize and deduplicate but preserve provider order
        forms = [str(f).strip() for f in (forms or []) if str(f).strip()]
        dedup_forms = list(dict.fromkeys(forms))

        # Freeze the order once
        if not self._forms_order:
            self._forms_order = dedup_forms[:]

        # Early-exit: nothing changed; just sync selection
        if (
            self._forms_cache_identifier == identifier
            and self._forms_cache_list == self._forms_order
            and self.form_combo.count() > 0
        ):
            self.form_combo.setEnabled(True)
            desired_text = self.form_combo.currentText().strip()
            if desired_text and self.form_combo.currentText() != desired_text:
                self.form_combo.blockSignals(True)
                self.form_combo.setCurrentText(desired_text)
                self.form_combo.blockSignals(False)
            return

        # Update cache
        self._forms_cache_identifier = identifier
        self._forms_cache_list = self._forms_order[:]

        # Rebuild using frozen order
        previous_choice = self.form_combo.currentText().strip() if self.form_combo.count() > 0 else ""
        self.form_combo.blockSignals(True)
        self.form_combo.clear()
        for item_text in self._forms_order:
            self.form_combo.addItem(item_text)
        self.form_combo.setEnabled(True)

        # Restore previous choice if present; otherwise keep first
        if previous_choice and previous_choice in self._forms_order:
            self.form_combo.setCurrentText(previous_choice)
        elif self._forms_order:
            self.form_combo.setCurrentText(self._forms_order[0])

        self.form_combo.blockSignals(False)

    # -------- Pokédex flavor (version combo + text) --------
    def _bind_pokedex_flavor(self, identifier: str, language_id: int | None = None):
        """Fetch versions + flavor texts and bind to the UI block."""
        self._flavor_versions = []
        self._flavor_texts = []

        if not hasattr(api, "get_pokedex_flavor"):
            self.dex_group.setEnabled(False)
            self.dex_combo.clear()
            self.lbl_flavor.setText("—")
            return

        try:
            lang = self.current_language_id if language_id is None else language_id
            res = api.get_pokedex_flavor(identifier, language_id=lang)
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

    # ---- Media ----------------------------------------------------------------

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
            self.audio.setVolume(0.8)  # 0–1
            self.player.play()
        except Exception as e:
            QMessageBox.warning(self, "Audio", f"Could not play cry:\n{e}")

    def _init_autocomplete(self):
        all_names = self._get_all_pokemon_names()
        self._all_pokemon_names = sorted(set(all_names), key=str.casefold)
        self._completer_model= QStringListModel(self._all_pokemon_names,self)
        self._completer= QCompleter(self._completer_model,self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

        self.input_name.setCompleter(self._completer)

        self.input_name.textEdited.connect(self._on_search_text_edited)
        self.input_name.returnPressed.connect(self._on_load_clicked)

    def _get_all_pokemon_names(self) -> list[str]:
        """Fetch all Pokémon names for autocomplete."""
        lang= self.current_language_id
        df=pokemon_species_names_df[pokemon_species_names_df['local_language_id']==lang]
        if df.empty:
            return pokemon_species_df['identifier'].str.capitalize().tolist()
        return df['name'].tolist()

    def _on_search_text_edited(self, text: str):
        """Update completer model based on current text."""
        #pattern = text.str().casefold()
        pattern = text.strip().casefold()

        if not pattern:
            self._completer_model.setStringList([])
            return
        matches = [name for name in self._all_pokemon_names if name.casefold().startswith(pattern)]
        self._completer_model.setStringList(matches[:10])
    


# ---- Entrypoint ---------------------------------------------------------------

def run():
    app = QApplication(sys.argv)
    w = PokedexWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    run()
