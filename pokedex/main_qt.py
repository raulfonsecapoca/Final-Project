"""
Pokedex page using PySide6.

This file expects pokedex.my_module.typed_function to expose:
- get_pokemon(identifier: str, form: str | None = None) -> dict
  returning keys: name, dex_number, image, cries (list[str]), types (list[str]),
  base_stats (dict[str,int]), evolution_line (list[dict{name,image}]), forms (list[str]|optional)
- (optional) get_available_forms(identifier) -> list[str]

If your API differs, just adapt the calls in _load_pokemon_data().
"""

import sys
import io
import os
import requests

import numpy as np  # kept because you used it earlier; remove if unused
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QPixmap, QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
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
    QSpacerItem,
    QGroupBox,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from pokedex.my_module import typed_function as api  # <— your data provider


def _load_pixmap(path_or_url: str, max_size: QSize | None = QSize(256, 256)) -> QPixmap:
    """Load image from local path or URL into QPixmap; optionally scale preserving aspect ratio."""
    try:
        if path_or_url.startswith(("http://", "https://")):
            resp = requests.get(path_or_url, timeout=10)
            resp.raise_for_status()
            data = resp.content
            pm = QPixmap()
            pm.loadFromData(data)
        else:
            pm = QPixmap(path_or_url)

        if not pm or pm.isNull():
            return QPixmap()

        if max_size is not None:
            pm = pm.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return pm
    except Exception:
        return QPixmap()


class PokedexWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pokédex")
        self.setMinimumSize(900, 650)
        # --- Window icon ---
        self.setWindowIcon(QIcon("data/sprites/sprites/items/poke-ball.png"))


        # Media player (for cries)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)

        # --- Top: search bar + form selector + buttons
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Enter Pokémon name or number (e.g., pikachu or 25)")
        self.btn_load = QPushButton("Load")
        self.btn_play_cry = QPushButton("Play Cry")
        self.btn_play_cry.setEnabled(False)

        self.form_combo = QComboBox()
        self.form_combo.setEnabled(False)
        # Make the combo box wide enough to display full text
        self.form_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.form_combo.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.form_combo.setMinimumContentsLength(12)  # optional: tweak to your dataset



        # Cache to avoid unnecessary rebuilds + track base form name (the Pokémon name)
        self._forms_cache_identifier = None
        self._forms_cache_list = None  # list[str] excluding the base name
        self._base_form_name = ""      # equals to current Pokémon 'name'



        top_row = QHBoxLayout()
        top_row.addWidget(self.input_name, 3)
        top_row.addWidget(self.btn_load, 0)
        top_row.addSpacing(12)
        top_row.addWidget(QLabel("Form:"), 0)
        top_row.addWidget(self.form_combo, 0)
        top_row.addSpacing(12)
        top_row.addWidget(self.btn_play_cry, 0)

        # --- Left: main sprite + name + types + dex
        self.lbl_sprite = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl_sprite.setFrameShape(QFrame.Shape.Panel)
        self.lbl_sprite.setFrameShadow(QFrame.Shadow.Sunken)
        self.lbl_sprite.setMinimumSize(256, 256)

        self.lbl_name = QLabel("<b>Name</b>")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_dex = QLabel("Dex #: —")
        self.lbl_dex.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.types_row = QHBoxLayout()
        self.types_row.addStretch()

        left_col = QVBoxLayout()
        left_col.addWidget(self.lbl_sprite)
        left_col.addSpacing(8)
        left_col.addWidget(self.lbl_name)
        left_col.addWidget(self.lbl_dex)
        left_col.addLayout(self.types_row)
        left_col.addStretch()

        # --- Right top: base stats grid
        self.stats_grid = QGridLayout()
        self.stats_labels = {}
        stat_names = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
        for r, s in enumerate(stat_names):
            k = QLabel(f"{s}:")
            v = QLabel("—")
            self.stats_labels[s] = v
            self.stats_grid.addWidget(k, r, 0, alignment=Qt.AlignmentFlag.AlignRight)
            self.stats_grid.addWidget(v, r, 1, alignment=Qt.AlignmentFlag.AlignLeft)

        stats_group = QGroupBox("Base Stats")
        sg_layout = QVBoxLayout()
        sg_layout.addLayout(self.stats_grid)
        stats_group.setLayout(sg_layout)

        # --- Right bottom: evolution line (scrollable row of image+name)
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

        # --- Main 2-column area
        main_row = QHBoxLayout()
        main_row.addLayout(left_col, 1)
        main_row.addLayout(right_col, 2)

        # --- Root layout
        root = QVBoxLayout(self)
        root.addLayout(top_row)
        root.addSpacing(6)
        root.addLayout(main_row, 1)

        # --- Signals
        self.btn_load.clicked.connect(self._on_load_clicked)
        self.btn_play_cry.clicked.connect(self._on_play_cry_clicked)
        # Change form automatically when the combo changes
        self.form_combo.currentTextChanged.connect(self._on_form_changed)

        # State
        self.current_identifier = None
        self.current_data = {}
        self.current_cry_index = 0

    # -------------------- Data loading and UI binding --------------------

    def _on_load_clicked(self):
        """Handle the Load button click; fetch by name/number."""
        ident = self.input_name.text().strip()
        if not ident:
            QMessageBox.warning(self, "Pokédex", "Please type a Pokémon name or number.")
            return
        self.current_identifier = ident
        self._load_pokemon_data(identifier=ident, form=None)

    def _on_form_changed(self, form_text: str):
        """Auto-apply selected form; base form is the Pokémon name."""
        if not self.current_identifier:
            return

        # If the selected text equals the base form (Pokémon name), treat as default
        if form_text == self._base_form_name:
            self._load_pokemon_data(identifier=self.current_identifier, form=None)
        else:
            self._load_pokemon_data(identifier=self.current_identifier, form=form_text)


    def _load_pokemon_data(self, identifier: str, form: str | None):
        """Calls your API (typed_function) and binds the result to the UI."""
        try:
            # Preferred shape: typed_function.get_pokemon(...)
            if hasattr(api, "get_pokemon"):
                data = api.get_pokemon(identifier, form=form)
            else:
                # Fallback: typed_function returns a dict given identifier
                # (adjust this to your real function signature if needed)
                data = api(identifier)  # type: ignore

            if not isinstance(data, dict):
                raise ValueError("typed_function.get_pokemon must return a dict")

            self.current_data = data
            self._bind_header(data)
            self._bind_types(data.get("types", []))
            self._bind_stats(data.get("base_stats", {}))
            self._bind_evolution_line(data.get("evolution_line", []))
            self._bind_forms(identifier, data)

            # Cries
            cries = data.get("cries") or []
            self.btn_play_cry.setEnabled(bool(cries))
            self.current_cry_index = 0

        except Exception as e:
            QMessageBox.critical(self, "Error loading Pokémon", str(e))

    # ---- Binders

    def _bind_header(self, data: dict):
        """Bind name, dex number and main sprite."""
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

    def _bind_types(self, types: list[str]):
        """Render type chips; clear and rebuild row."""
        # Clear previous
        while self.types_row.count() > 0:
            item = self.types_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        # Add new
        self.types_row.addStretch()
        for t in types:
            chip = QLabel(t)
            chip.setStyleSheet(
                "QLabel { padding: 4px 8px; border-radius: 12px; border: 1px solid #999; }"
            )
            self.types_row.addWidget(chip, 0)
        self.types_row.addStretch()

    def _bind_stats(self, stats: dict):
        """Bind base stats; accepts uppercase or lowercase keys."""
        for key, lbl in self.stats_labels.items():
            val = stats.get(key) or stats.get(key.lower()) or "—"
            lbl.setText(str(val))

    def _bind_evolution_line(self, evo_list: list[dict]):
        """Render evolution cards horizontally inside a scroll area."""
        # Clear row
        while self.evo_row.count() > 0:
            item = self.evo_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        # Rebuild
        for node in evo_list:
            w = self._make_evo_card(node.get("name", "?"), node.get("image"))
            self.evo_row.addWidget(w)
        self.evo_row.addStretch()

    def _make_evo_card(self, name: str, image: str | None) -> QWidget:
        """Create a small card with sprite, name and a button to open that Pokémon."""
        box = QVBoxLayout()
        img = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        pm = _load_pixmap(image, QSize(96, 96)) if image else QPixmap()
        if pm.isNull():
            img.setText("—")
        else:
            img.setPixmap(pm)
        nm = QLabel(name, alignment=Qt.AlignmentFlag.AlignCenter)
        nm.setWordWrap(True)

        # Clickable to load that Pokémon by name (adjust if you need to use IDs)
        btn = QPushButton("View")
        btn.clicked.connect(lambda: self._load_pokemon_data(identifier=name, form=None))

        cont = QWidget()
        box.addWidget(img)
        box.addWidget(nm)
        box.addWidget(btn)
        cont.setLayout(box)
        cont.setMinimumWidth(120)
        return cont

    def _bind_forms(self, identifier: str, data: dict):
        """Populate combo with [base name] + other forms; keep selection stable."""
        # Base form is the Pokémon's own name
        base_name = data.get("name") or ""
        self._base_form_name = base_name

        # Fetch forms list (other/alternate forms)
        forms = data.get("forms")
        if forms is None and hasattr(api, "get_available_forms"):
            try:
                forms = api.get_available_forms(identifier)
            except Exception:
                forms = None

        # Normalize and ensure we don't duplicate the base name in 'forms'
        forms = [str(f) for f in (forms or []) if str(f).strip() and str(f) != base_name]

        # If nothing changed (same identifier and same forms), don't rebuild
        if (
            self._forms_cache_identifier == identifier
            and self._forms_cache_list == forms
            and self.form_combo.count() > 0
        ):
            # Ensure it's enabled if there is at least the base item
            self.form_combo.setEnabled(True)
            # Also ensure the current selection reflects API's current form
            current_form = data.get("form")
            desired_text = base_name if not current_form else str(current_form)
            if self.form_combo.currentText() != desired_text:
                self.form_combo.blockSignals(True)
                self.form_combo.setCurrentText(desired_text)
                self.form_combo.blockSignals(False)
            return

        # Update cache
        self._forms_cache_identifier = identifier
        self._forms_cache_list = forms

        # Rebuild combo: first item is ALWAYS the base form (Pokémon name)
        self.form_combo.blockSignals(True)
        self.form_combo.clear()
        self.form_combo.addItem(base_name)
        for f in forms:
            self.form_combo.addItem(f)
        self.form_combo.setEnabled(True)

        # Select current form reported by API (None/default -> base_name)
        current_form = data.get("form")
        desired_text = base_name if not current_form else str(current_form)
        self.form_combo.setCurrentText(desired_text)

        self.form_combo.blockSignals(False)


    # -------------------- Media --------------------

    def _on_play_cry_clicked(self):
        """Play next cry in sequence."""
        cries = self.current_data.get("cries") or []
        if not cries:
            return
        url = cries[self.current_cry_index % len(cries)]
        self.current_cry_index += 1
        self._play_audio(url)

    def _play_audio(self, url_or_path: str):
        """Play audio from URL or local path."""
        try:
            if url_or_path.startswith(("http://", "https://")):
                self.player.setSource(QUrl(url_or_path))
            else:
                self.player.setSource(QUrl.fromLocalFile(os.path.abspath(url_or_path)))
            self.audio.setVolume(0.8)  # 0–1
            self.player.play()
        except Exception as e:
            QMessageBox.warning(self, "Audio", f"Could not play cry:\n{e}")


def run():
    """Main entrypoint."""
    app = QApplication(sys.argv)
    w = PokedexWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    run()
