"""
any2notes — SettingsPanel
Preferenze persistenti: percorso Python, Pandoc, parametri default, CUDA opt-in.
Le impostazioni vengono salvate in settings.json nella root dell'app.
"""

import json
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QFileDialog, QMessageBox, QSpinBox,
    QComboBox, QGroupBox,
)

SETTINGS_FILE = Path(__file__).parent.parent.parent / "settings.json"

DEFAULTS = {
    "python_path": "",           # vuoto = usa sys.executable
    "pandoc_path": "",           # vuoto = cerca in PATH / bin/
    "default_model_whisper": "turbo",
    "default_language": "it",
    "default_beam_size": 3,
    "default_ollama_model": "gemma4",
    "default_chunk_size": 4000,
    "cuda_available": False,     # utente conferma di avere CUDA + torch
    "ollama_host": "http://localhost:11434",
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


class SettingsPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = load_settings()
        self._build_ui()
        self._populate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        title = QLabel("Impostazioni")
        title.setObjectName("label_title")
        root.addWidget(title)

        # ── Percorsi ── #
        paths_group = self._group("Percorsi")
        pg = QVBoxLayout(paths_group)
        pg.setSpacing(12)

        pg.addWidget(self._section_lbl("Python (lascia vuoto per usare quello di sistema)"))
        self._python_edit, python_row = self._path_row("python.exe", "Seleziona python.exe")
        pg.addLayout(python_row)

        pg.addWidget(self._section_lbl("Pandoc (lascia vuoto per cercare in PATH / bin/)"))
        self._pandoc_edit, pandoc_row = self._path_row("pandoc.exe", "Seleziona pandoc.exe")
        pg.addLayout(pandoc_row)

        pg.addWidget(self._section_lbl("Host Ollama"))
        self._ollama_host_edit = QLineEdit()
        pg.addWidget(self._ollama_host_edit)

        root.addWidget(paths_group)

        # ── Whisper defaults ── #
        whisper_group = self._group("Trascrizione — valori predefiniti")
        wg = QVBoxLayout(whisper_group)
        wg.setSpacing(12)

        row1 = QHBoxLayout()
        row1.setSpacing(20)

        col_model = QVBoxLayout()
        col_model.addWidget(self._section_lbl("Modello"))
        self._wmodel_combo = QComboBox()
        self._wmodel_combo.addItems(["turbo", "large-v3"])
        col_model.addWidget(self._wmodel_combo)

        col_lang = QVBoxLayout()
        col_lang.addWidget(self._section_lbl("Lingua"))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["it", "en"])
        col_lang.addWidget(self._lang_combo)

        col_beam = QVBoxLayout()
        col_beam.addWidget(self._section_lbl("Beam size"))
        self._beam_spin = QSpinBox()
        self._beam_spin.setRange(1, 10)
        col_beam.addWidget(self._beam_spin)

        row1.addLayout(col_model)
        row1.addLayout(col_lang)
        row1.addLayout(col_beam)
        row1.addStretch()
        wg.addLayout(row1)

        self._cuda_check = QCheckBox(
            "Ho installato CUDA + torch / ctranslate2-CUDA  "
            "(abilita engine Whisper CUDA nella UI)"
        )
        wg.addWidget(self._cuda_check)

        root.addWidget(whisper_group)

        # ── Ollama defaults ── #
        ollama_group = self._group("Riassunto — valori predefiniti")
        og = QVBoxLayout(ollama_group)
        og.setSpacing(12)

        row2 = QHBoxLayout()
        row2.setSpacing(20)

        col_omodel = QVBoxLayout()
        col_omodel.addWidget(self._section_lbl("Modello Ollama"))
        self._omodel_edit = QLineEdit()
        self._omodel_edit.setPlaceholderText("gemma4")
        col_omodel.addWidget(self._omodel_edit)

        col_chunk = QVBoxLayout()
        col_chunk.addWidget(self._section_lbl("Chunk size"))
        self._chunk_spin = QSpinBox()
        self._chunk_spin.setRange(500, 32000)
        self._chunk_spin.setSingleStep(500)
        col_chunk.addWidget(self._chunk_spin)

        row2.addLayout(col_omodel)
        row2.addLayout(col_chunk)
        row2.addStretch()
        og.addLayout(row2)
        root.addWidget(ollama_group)

        # ── Save ── #
        btn_row = QHBoxLayout()
        self._btn_save = QPushButton("Salva impostazioni")
        self._btn_save.setObjectName("btn_primary")
        self._btn_save.clicked.connect(self._save)
        self._btn_reset = QPushButton("Ripristina default")
        self._btn_reset.setObjectName("btn_ghost")
        self._btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_reset)
        btn_row.addStretch()
        root.addLayout(btn_row)
        root.addStretch()

    # ------------------------------------------------------------------ #

    def _group(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                color: #8fa882;
                font-size: 12px;
                font-weight: 500;
                border: 1px solid #2e352d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 4px;
                color: #5a6d54;
            }
        """)
        return g

    def _section_lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("label_section")
        return l

    def _path_row(self, placeholder: str, dialog_title: str):
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        btn = QPushButton("Sfoglia…")
        btn.setObjectName("btn_ghost")
        btn.setFixedWidth(80)
        btn.clicked.connect(lambda: self._browse_path(edit, dialog_title))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(edit)
        row.addWidget(btn)
        return edit, row

    def _browse_path(self, edit: QLineEdit, title: str):
        path, _ = QFileDialog.getOpenFileName(self, title, "", "Eseguibile (*.exe)")
        if path:
            edit.setText(path)

    def _populate(self):
        s = self._settings
        self._python_edit.setText(s.get("python_path", ""))
        self._pandoc_edit.setText(s.get("pandoc_path", ""))
        self._ollama_host_edit.setText(s.get("ollama_host", DEFAULTS["ollama_host"]))
        idx = self._wmodel_combo.findText(s.get("default_model_whisper", "turbo"))
        if idx >= 0:
            self._wmodel_combo.setCurrentIndex(idx)
        idx2 = self._lang_combo.findText(s.get("default_language", "it"))
        if idx2 >= 0:
            self._lang_combo.setCurrentIndex(idx2)
        self._beam_spin.setValue(s.get("default_beam_size", 3))
        self._cuda_check.setChecked(s.get("cuda_available", False))
        self._omodel_edit.setText(s.get("default_ollama_model", "gemma4"))
        self._chunk_spin.setValue(s.get("default_chunk_size", 4000))

    def _save(self):
        self._settings.update({
            "python_path":            self._python_edit.text().strip(),
            "pandoc_path":            self._pandoc_edit.text().strip(),
            "ollama_host":            self._ollama_host_edit.text().strip(),
            "default_model_whisper":  self._wmodel_combo.currentText(),
            "default_language":       self._lang_combo.currentText(),
            "default_beam_size":      self._beam_spin.value(),
            "cuda_available":         self._cuda_check.isChecked(),
            "default_ollama_model":   self._omodel_edit.text().strip(),
            "default_chunk_size":     self._chunk_spin.value(),
        })
        save_settings(self._settings)
        QMessageBox.information(self, "Salvato", "Impostazioni salvate correttamente.")

    def _reset(self):
        self._settings = dict(DEFAULTS)
        self._populate()
