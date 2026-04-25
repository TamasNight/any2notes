"""
any2notes — Step Panels
Un QWidget per ogni step della pipeline.
Ogni panel riceve il RunManager corrente e gestisce autonomamente
parametri, lancio script, output e versionamento.
"""

import os
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QFileDialog, QMessageBox,
    QButtonGroup, QRadioButton, QGroupBox, QSizePolicy, QLineEdit,
)

from app.core.run_manager import RunManager, STATUS_DONE, STATUS_IDLE, STATUS_RUNNING, STATUS_ERROR
from app.core.runner import ScriptRunner
from app.core import settings as app_settings
from app.ui.widgets import LogView, VersionSelector, FileDropButton, StatusPill, make_separator


# ── Helper ────────────────────────────────────────────────────────────── #

def _card(parent=None) -> QWidget:
    w = QWidget(parent)
    w.setObjectName("card")
    return w


def _label_section(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("label_section")
    return l


def _label_muted(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("label_muted")
    return l


def _primary_btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("btn_primary")
    return b


def _ghost_btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("btn_ghost")
    return b


# ══════════════════════════════════════════════════════════════════════════
#  STEP 1 — Trascrizione
# ══════════════════════════════════════════════════════════════════════════

class Step1Panel(QWidget):
    """
    Wrapper per speech2text.py / fast-speech2text.py.
    Permette di scegliere engine, modello, lingua, beam_size.
    """

    step_completed = pyqtSignal()

    STEP_ID = "step1_transcribe"

    def __init__(self, ollama_service, parent=None):
        super().__init__(parent)
        self._run: RunManager | None = None
        self._runner = ScriptRunner(self)
        self._runner.stdout_line.connect(lambda l: self._log.append_stdout(l))
        self._runner.stderr_line.connect(lambda l: self._log.append_stderr(l))
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(lambda e: self._log.append_stderr(f"ERRORE: {e}"))
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Titolo
        title = QLabel("Trascrizione audio")
        title.setObjectName("label_title")
        root.addWidget(title)
        root.addWidget(_label_muted("speech2text.py / fast-speech2text.py"))
        root.addWidget(make_separator())

        # File input
        card1 = _card()
        c1l = QVBoxLayout(card1)
        c1l.setSpacing(10)
        c1l.addWidget(_label_section("File audio"))
        self._file_btn = FileDropButton(
            "Trascina file audio o clicca per sfogliare",
            "Audio (*.mp3 *.wav *.m4a *.ogg *.flac *.mp4 *.mkv *.webm)",
        )
        self._file_btn.file_selected.connect(self._on_file_selected)
        c1l.addWidget(self._file_btn)
        root.addWidget(card1)

        # Parametri
        card2 = _card()
        c2l = QVBoxLayout(card2)
        c2l.setSpacing(12)
        c2l.addWidget(_label_section("Parametri"))

        # Engine
        row_engine = QHBoxLayout()
        row_engine.addWidget(QLabel("Engine:"))
        self._engine_group = QButtonGroup(self)
        for i, (label, val) in enumerate([("Whisper CUDA", "cuda"), ("Faster-Whisper CPU", "cpu")]):
            rb = QRadioButton(label)
            self._engine_group.addButton(rb, i)
            if i == 1:
                rb.setChecked(True)
            row_engine.addWidget(rb)
        row_engine.addStretch()
        c2l.addLayout(row_engine)

        # Modello / Lingua / Beam
        row_params = QHBoxLayout()
        row_params.setSpacing(16)

        col_model = QVBoxLayout()
        col_model.addWidget(QLabel("Modello:"))
        self._model_combo = QComboBox()
        self._model_combo.addItems(["turbo", "large-v3"])
        col_model.addWidget(self._model_combo)

        col_lang = QVBoxLayout()
        col_lang.addWidget(QLabel("Lingua:"))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["it", "en"])
        col_lang.addWidget(self._lang_combo)

        col_beam = QVBoxLayout()
        col_beam.addWidget(QLabel("Beam size:"))
        self._beam_spin = QSpinBox()
        self._beam_spin.setRange(1, 10)
        self._beam_spin.setValue(3)
        col_beam.addWidget(self._beam_spin)

        row_params.addLayout(col_model)
        row_params.addLayout(col_lang)
        row_params.addLayout(col_beam)
        row_params.addStretch()
        c2l.addLayout(row_params)
        root.addWidget(card2)

        # Log
        card3 = _card()
        c3l = QVBoxLayout(card3)
        c3l.addWidget(_label_section("Output"))
        self._log = LogView()
        self._log.setMinimumHeight(120)
        c3l.addWidget(self._log)
        root.addWidget(card3)

        # Azioni
        row_actions = QHBoxLayout()
        self._btn_run = _primary_btn("Avvia trascrizione →")
        self._btn_run.clicked.connect(self._run_script)
        self._btn_stop = QPushButton("Interrompi")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._runner.stop)
        self._btn_export = _ghost_btn("Esporta output")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._export)
        row_actions.addWidget(self._btn_run)
        row_actions.addWidget(self._btn_stop)
        row_actions.addStretch()
        row_actions.addWidget(self._btn_export)
        root.addLayout(row_actions)
        root.addStretch()

    def set_run(self, run: RunManager):
        self._run = run
        self._log.clear_log()
        step = run.step_data(self.STEP_ID)
        versions = step["versions"]
        if versions:
            self._log.append_info(f"Step precedente: {len(versions)} versione/i disponibili")
        self._update_buttons()

    def _on_file_selected(self, path: str):
        self._log.append_info(f"File selezionato: {Path(path).name}")

    def _update_buttons(self):
        has_output = bool(self._run and self._run.step_versions(self.STEP_ID))
        self._btn_export.setEnabled(has_output)

    def _collect_params(self) -> dict:
        return {
            "model": self._model_combo.currentText(),
            "lang": self._lang_combo.currentText(),
            "beam_size": self._beam_spin.value(),
            "engine": "cuda" if self._engine_group.checkedId() == 0 else "cpu",
        }

    def _run_script(self):
        if not self._run:
            return
        if not self._file_btn.path:
            QMessageBox.warning(self, "File mancante", "Seleziona un file audio prima di avviare.")
            return

        # Chiedi overwrite / nuova versione se già esiste output
        versions = self._run.step_versions(self.STEP_ID)
        overwrite_v = None
        if versions:
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox
            mb = QMessageBox(self)
            mb.setWindowTitle("Output esistente")
            mb.setText("Questo step ha già degli output.\nVuoi sovrascrivere l'ultima versione o crearne una nuova?")
            btn_overwrite = mb.addButton("Sovrascrivi", QMessageBox.ButtonRole.DestructiveRole)
            btn_new = mb.addButton("Nuova versione", QMessageBox.ButtonRole.AcceptRole)
            mb.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
            mb.exec()
            clicked = mb.clickedButton()
            if clicked is None or clicked.text() == "Annulla":
                return
            if clicked is btn_overwrite:
                overwrite_v = versions[-1]["v"]

        params = self._collect_params()
        v_num = overwrite_v if overwrite_v else (max((v["v"] for v in versions), default=0) + 1)
        out_dir = self._run.run_dir / self.STEP_ID
        out_file = out_dir / f"output_v{v_num}.txt"

        script = "speech2text.py" if params["engine"] == "cuda" else "fast-speech2text.py"
        args = [
            self._file_btn.path,
            str(out_file),
            params["model"],
            params["lang"],
            str(params["beam_size"]),
        ]
        if params["engine"] == "cpu":
            args.append("cpu")

        self._run.set_step_status(self.STEP_ID, STATUS_RUNNING)
        self._pending_params = params
        self._pending_overwrite = overwrite_v
        self._pending_outfile = str(out_file)
        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._log.append_info(f"▶ Avvio {script}…")
        self._runner.run(script, args)

    def _on_finished(self, exit_code: int):
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        if exit_code == 0:
            self._run.add_version(
                self.STEP_ID,
                Path(self._pending_outfile).name,
                self._pending_params,
                self._pending_overwrite,
            )
            self._run.set_step_status(self.STEP_ID, STATUS_DONE)
            self._log.append_info("✓ Trascrizione completata.")
            self._btn_export.setEnabled(True)
            self.step_completed.emit()
        else:
            self._run.set_step_status(self.STEP_ID, STATUS_ERROR)
            self._log.append_stderr(f"✗ Processo terminato con codice {exit_code}.")

    def _export(self):
        if not self._run:
            return
        v = self._run.selected_version(self.STEP_ID)
        if not v:
            return
        src = self._run.run_dir / self.STEP_ID / v["file"]
        dst, _ = QFileDialog.getSaveFileName(self, "Esporta trascrizione", v["file"], "Testo (*.txt)")
        if dst:
            import shutil
            shutil.copy2(src, dst)


# ══════════════════════════════════════════════════════════════════════════
#  STEP 2 — Riassunto  (summary.py + summarize_lecture.py)
# ══════════════════════════════════════════════════════════════════════════

class Step2Panel(QWidget):
    """
    Step 2: riassunto generico (summary.py) o di lezione (summarize_lecture.py).
    L'utente può scegliere quale modalità usare.
    """

    step_completed = pyqtSignal()
    STEP_ID = "step2_summarize"
    PREV_STEP_ID = "step1_transcribe"

    def __init__(self, ollama_service, parent=None):
        super().__init__(parent)
        self._run: RunManager | None = None
        self._ollama = ollama_service
        self._runner = ScriptRunner(self)
        self._runner.stdout_line.connect(lambda l: self._log.append_stdout(l))
        self._runner.stderr_line.connect(lambda l: self._log.append_stderr(l))
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(lambda e: self._log.append_stderr(f"ERRORE: {e}"))
        self._pending_params = {}
        self._pending_overwrite = None
        self._pending_outfile = ""
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("Riassunto")
        title.setObjectName("label_title")
        root.addWidget(title)

        # Modalità: generico vs lezione
        mode_card = _card()
        ml = QVBoxLayout(mode_card)
        ml.addWidget(_label_section("Modalità"))
        self._mode_group = QButtonGroup(self)
        self._rb_generic = QRadioButton("Testo generico  (summary.py)")
        self._rb_lecture = QRadioButton("Riassunto lezione  (summarize_lecture.py + PPTX)")
        self._rb_generic.setChecked(True)
        self._mode_group.addButton(self._rb_generic, 0)
        self._mode_group.addButton(self._rb_lecture, 1)
        self._rb_generic.toggled.connect(self._on_mode_changed)
        ml.addWidget(self._rb_generic)
        ml.addWidget(self._rb_lecture)
        root.addWidget(mode_card)

        # Input
        input_card = _card()
        il = QVBoxLayout(input_card)
        il.setSpacing(10)

        # Versioni step1
        self._ver_selector = VersionSelector("trascrizione (step 1)", "Testo (*.txt)")
        self._ver_selector.version_selected.connect(self._on_version_selected)
        self._ver_selector.external_file_selected.connect(self._on_external_txt)
        il.addWidget(self._ver_selector)

        # PPTX (solo modalità lezione)
        self._pptx_label = _label_section("File PPTX")
        self._pptx_btn = FileDropButton("Trascina .pptx o clicca per sfogliare", "PowerPoint (*.pptx)")
        self._pptx_btn.file_selected.connect(lambda p: None)
        self._pptx_label.hide()
        self._pptx_btn.hide()
        il.addWidget(self._pptx_label)
        il.addWidget(self._pptx_btn)

        root.addWidget(input_card)

        # Parametri
        param_card = _card()
        pl = QVBoxLayout(param_card)
        pl.setSpacing(12)
        pl.addWidget(_label_section("Parametri"))

        row1 = QHBoxLayout()
        row1.setSpacing(16)

        col_model = QVBoxLayout()
        col_model.addWidget(QLabel("Modello Ollama:"))
        self._model_combo = QComboBox()
        self._model_combo.addItems(["gemma4", "qwen3.6", "minimax-m2.7:cloud"])
        col_model.addWidget(self._model_combo)

        col_chunk = QVBoxLayout()
        col_chunk.addWidget(QLabel("Chunk size:"))
        self._chunk_spin = QSpinBox()
        self._chunk_spin.setRange(500, 32000)
        self._chunk_spin.setValue(4000)
        self._chunk_spin.setSingleStep(500)
        col_chunk.addWidget(self._chunk_spin)

        row1.addLayout(col_model)
        row1.addLayout(col_chunk)
        row1.addStretch()
        pl.addLayout(row1)

        row2 = QHBoxLayout()
        self._parts_check = QCheckBox("Salva parti separate  (-p)")
        self._slides_only_check = QCheckBox("Solo slide, no trascrizione  (--slides-only)")
        self._no_images_check = QCheckBox("Non inviare immagini  (--no-images)")
        self._slides_only_check.hide()
        self._no_images_check.hide()
        row2.addWidget(self._parts_check)
        row2.addWidget(self._slides_only_check)
        row2.addWidget(self._no_images_check)
        row2.addStretch()
        pl.addLayout(row2)

        # max-images (solo lezione)
        self._max_img_row = QHBoxLayout()
        self._max_img_label = QLabel("Max immagini:")
        self._max_img_spin = QSpinBox()
        self._max_img_spin.setRange(1, 100)
        self._max_img_spin.setValue(20)
        self._max_img_row_widget = QWidget()
        self._max_img_row_widget.setLayout(self._max_img_row)
        self._max_img_row.addWidget(self._max_img_label)
        self._max_img_row.addWidget(self._max_img_spin)
        self._max_img_row.addStretch()
        self._max_img_row_widget.hide()
        pl.addWidget(self._max_img_row_widget)

        root.addWidget(param_card)

        # Log
        log_card = _card()
        ll = QVBoxLayout(log_card)
        ll.addWidget(_label_section("Output"))
        self._log = LogView()
        self._log.setMinimumHeight(100)
        ll.addWidget(self._log)
        root.addWidget(log_card)

        # Azioni
        row_actions = QHBoxLayout()
        self._btn_run = _primary_btn("Avvia riassunto →")
        self._btn_run.clicked.connect(self._run_script)
        self._btn_stop = QPushButton("Interrompi")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._runner.stop)
        self._btn_export = _ghost_btn("Esporta .md")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._export)
        row_actions.addWidget(self._btn_run)
        row_actions.addWidget(self._btn_stop)
        row_actions.addStretch()
        row_actions.addWidget(self._btn_export)
        root.addLayout(row_actions)
        root.addStretch()

        self._selected_input_path: str | None = None

    def _on_mode_changed(self, generic_checked: bool):
        is_lecture = not generic_checked
        self._pptx_label.setVisible(is_lecture)
        self._pptx_btn.setVisible(is_lecture)
        self._slides_only_check.setVisible(is_lecture)
        self._no_images_check.setVisible(is_lecture)
        self._max_img_row_widget.setVisible(is_lecture)

    def set_run(self, run: RunManager):
        self._run = run
        self._log.clear_log()
        versions = run.step_versions(self.PREV_STEP_ID)
        sel = run.step_data(self.PREV_STEP_ID)["selected_version"]
        self._ver_selector.set_versions(versions, sel)
        if versions:
            sel_v = run.selected_version(self.PREV_STEP_ID)
            if sel_v:
                p = run.run_dir / self.PREV_STEP_ID / sel_v["file"]
                self._selected_input_path = str(p)
        self._update_ollama_models()

    def _update_ollama_models(self):
        if self._ollama and self._ollama.is_running:
            self._model_combo.clear()
            self._model_combo.addItems(self._ollama.all_models)

    def _on_version_selected(self, v_num: int):
        if self._run:
            self._run.select_version(self.PREV_STEP_ID, v_num)
            p = self._run.run_dir / self.PREV_STEP_ID / f"output_v{v_num}.txt"
            self._selected_input_path = str(p)

    def _on_external_txt(self, path: str):
        self._selected_input_path = path

    def _run_script(self):
        if not self._run:
            return
        if not self._selected_input_path:
            QMessageBox.warning(self, "Input mancante", "Seleziona un file di trascrizione.")
            return

        is_lecture = self._mode_group.checkedId() == 1
        if is_lecture and not self._pptx_btn.path:
            QMessageBox.warning(self, "PPTX mancante", "Seleziona un file .pptx per il riassunto lezione.")
            return

        versions = self._run.step_versions(self.STEP_ID)
        overwrite_v = None
        if versions:
            mb = QMessageBox(self)
            mb.setWindowTitle("Output esistente")
            mb.setText("Questo step ha già degli output.\nVuoi sovrascrivere o creare una nuova versione?")
            btn_ow = mb.addButton("Sovrascrivi", QMessageBox.ButtonRole.DestructiveRole)
            mb.addButton("Nuova versione", QMessageBox.ButtonRole.AcceptRole)
            mb.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
            mb.exec()
            clicked = mb.clickedButton()
            if clicked is None or clicked.text() == "Annulla":
                return
            if clicked is btn_ow:
                overwrite_v = versions[-1]["v"]

        v_num = overwrite_v if overwrite_v else (max((v["v"] for v in versions), default=0) + 1)
        out_dir = self._run.run_dir / self.STEP_ID
        out_file = out_dir / f"output_v{v_num}.md"

        model = self._model_combo.currentText()
        chunk = self._chunk_spin.value()
        parts = self._parts_check.isChecked()

        if not is_lecture:
            script = "summary.py"
            args = ["-i", self._selected_input_path, "-o", str(out_file), "-m", model,
                    "-c", str(chunk)]
            if parts:
                args.append("-p")
            params = {"mode": "generico", "model": model, "chunk": chunk}
        else:
            script = "summarize_lecture.py"
            args = [self._pptx_btn.path]
            if not self._slides_only_check.isChecked():
                args.append(self._selected_input_path)
            else:
                args.append("--slides-only")
            args += ["-m", model, "-o", str(out_file)]
            if self._no_images_check.isChecked():
                args.append("-ni")
            args += ["--max-images", str(self._max_img_spin.value())]
            params = {"mode": "lezione", "model": model}

        self._pending_params = params
        self._pending_overwrite = overwrite_v
        self._pending_outfile = str(out_file)
        self._run.set_step_status(self.STEP_ID, STATUS_RUNNING)
        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._log.append_info(f"▶ Avvio {script}…")
        self._runner.run(script, args)

    def _on_finished(self, exit_code: int):
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        if exit_code == 0:
            self._run.add_version(self.STEP_ID, Path(self._pending_outfile).name,
                                  self._pending_params, self._pending_overwrite)
            self._run.set_step_status(self.STEP_ID, STATUS_DONE)
            self._log.append_info("✓ Riassunto completato.")
            self._btn_export.setEnabled(True)
            self.step_completed.emit()
        else:
            self._run.set_step_status(self.STEP_ID, STATUS_ERROR)
            self._log.append_stderr(f"✗ Codice uscita: {exit_code}")

    def _export(self):
        if not self._run:
            return
        v = self._run.selected_version(self.STEP_ID)
        if not v:
            return
        src = self._run.run_dir / self.STEP_ID / v["file"]
        dst, _ = QFileDialog.getSaveFileName(self, "Esporta riassunto", v["file"], "Markdown (*.md)")
        if dst:
            import shutil
            shutil.copy2(src, dst)


# ══════════════════════════════════════════════════════════════════════════
#  STEP 3 — Esporta documento  (md2doc.py)
# ══════════════════════════════════════════════════════════════════════════

class Step3Panel(QWidget):
    """Converte il .md in .docx o .pdf tramite md2doc.py + pandoc."""

    step_completed = pyqtSignal()
    STEP_ID = "step3_export"
    PREV_STEP_ID = "step2_summarize"

    def __init__(self, ollama_service, parent=None):
        super().__init__(parent)
        self._run: RunManager | None = None
        self._runner = ScriptRunner(self)
        self._runner.stdout_line.connect(lambda l: self._log.append_stdout(l))
        self._runner.stderr_line.connect(lambda l: self._log.append_stderr(l))
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(lambda e: self._log.append_stderr(f"ERRORE: {e}"))
        self._pending_params = {}
        self._pending_overwrite = None
        self._pending_outfile = ""
        self._selected_input_path: str | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("Esporta documento")
        title.setObjectName("label_title")
        root.addWidget(title)
        root.addWidget(_label_muted("md2doc.py — conversione Markdown → DOCX / PDF tramite Pandoc"))
        root.addWidget(make_separator())

        # Input
        input_card = _card()
        il = QVBoxLayout(input_card)
        self._ver_selector = VersionSelector("riassunto (step 2)", "Markdown (*.md)")
        self._ver_selector.version_selected.connect(self._on_version_selected)
        self._ver_selector.external_file_selected.connect(lambda p: setattr(self, "_selected_input_path", p))
        il.addWidget(self._ver_selector)
        root.addWidget(input_card)

        # Formato
        fmt_card = _card()
        fl = QVBoxLayout(fmt_card)
        fl.addWidget(_label_section("Formato output"))
        self._fmt_group = QButtonGroup(self)
        self._rb_docx = QRadioButton("DOCX  (Word)")
        self._rb_pdf  = QRadioButton("PDF")
        self._rb_docx.setChecked(True)
        self._fmt_group.addButton(self._rb_docx, 0)
        self._fmt_group.addButton(self._rb_pdf, 1)
        row_fmt = QHBoxLayout()
        row_fmt.addWidget(self._rb_docx)
        row_fmt.addWidget(self._rb_pdf)
        row_fmt.addStretch()
        fl.addLayout(row_fmt)
        root.addWidget(fmt_card)

        # Log
        log_card = _card()
        ll = QVBoxLayout(log_card)
        ll.addWidget(_label_section("Output"))
        self._log = LogView()
        self._log.setMinimumHeight(100)
        ll.addWidget(self._log)
        root.addWidget(log_card)

        # Azioni
        row_actions = QHBoxLayout()
        self._btn_run = _primary_btn("Converti documento →")
        self._btn_run.clicked.connect(self._run_script)
        self._btn_stop = QPushButton("Interrompi")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._runner.stop)
        self._btn_export = _ghost_btn("Esporta file")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._export)
        row_actions.addWidget(self._btn_run)
        row_actions.addWidget(self._btn_stop)
        row_actions.addStretch()
        row_actions.addWidget(self._btn_export)
        root.addLayout(row_actions)
        root.addStretch()

    def set_run(self, run: RunManager):
        self._run = run
        self._log.clear_log()
        versions = run.step_versions(self.PREV_STEP_ID)
        sel = run.step_data(self.PREV_STEP_ID)["selected_version"]
        self._ver_selector.set_versions(versions, sel)
        if versions:
            sel_v = run.selected_version(self.PREV_STEP_ID)
            if sel_v:
                p = run.run_dir / self.PREV_STEP_ID / sel_v["file"]
                self._selected_input_path = str(p)

    def _on_version_selected(self, v_num: int):
        if self._run:
            self._run.select_version(self.PREV_STEP_ID, v_num)
            p = self._run.run_dir / self.PREV_STEP_ID / f"output_v{v_num}.md"
            self._selected_input_path = str(p)

    def _run_script(self):
        if not self._run or not self._selected_input_path:
            QMessageBox.warning(self, "Input mancante", "Seleziona un file .md da step 2.")
            return

        fmt = "pdf" if self._fmt_group.checkedId() == 1 else "docx"
        versions = self._run.step_versions(self.STEP_ID)
        overwrite_v = None
        if versions:
            mb = QMessageBox(self)
            mb.setWindowTitle("Output esistente")
            mb.setText("Vuoi sovrascrivere o creare una nuova versione?")
            btn_ow = mb.addButton("Sovrascrivi", QMessageBox.ButtonRole.DestructiveRole)
            mb.addButton("Nuova versione", QMessageBox.ButtonRole.AcceptRole)
            mb.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
            mb.exec()
            clicked = mb.clickedButton()
            if clicked is None or clicked.text() == "Annulla":
                return
            if clicked is btn_ow:
                overwrite_v = versions[-1]["v"]

        v_num = overwrite_v if overwrite_v else (max((v["v"] for v in versions), default=0) + 1)
        out_dir = self._run.run_dir / self.STEP_ID
        out_file = out_dir / f"output_v{v_num}.{fmt}"

        self._pending_params = {"format": fmt}
        self._pending_overwrite = overwrite_v
        self._pending_outfile = str(out_file)
        self._run.set_step_status(self.STEP_ID, STATUS_RUNNING)
        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._log.append_info(f"▶ Avvio md2doc.py → {fmt}…")
        self._runner.run("md2doc.py", [self._selected_input_path, "-f", fmt])

    def _on_finished(self, exit_code: int):
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        if exit_code == 0:
            self._run.add_version(self.STEP_ID, Path(self._pending_outfile).name,
                                  self._pending_params, self._pending_overwrite)
            self._run.set_step_status(self.STEP_ID, STATUS_DONE)
            self._log.append_info("✓ Documento creato.")
            self._btn_export.setEnabled(True)
            self.step_completed.emit()
        else:
            self._run.set_step_status(self.STEP_ID, STATUS_ERROR)
            self._log.append_stderr(f"✗ Codice uscita: {exit_code}")

    def _export(self):
        if not self._run:
            return
        v = self._run.selected_version(self.STEP_ID)
        if not v:
            return
        src = self._run.run_dir / self.STEP_ID / v["file"]
        fmt = self._pending_params.get("format", "docx")
        filt = "Word (*.docx)" if fmt == "docx" else "PDF (*.pdf)"
        dst, _ = QFileDialog.getSaveFileName(self, "Esporta documento", v["file"], filt)
        if dst:
            import shutil
            shutil.copy2(src, dst)
