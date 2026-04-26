"""
any2notes — BenchmarkPanel
Esegue test di velocità per speech2text e mostra storico risultati.
"""

import json
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QProgressBar, QComboBox, QMessageBox,
)

from app.core.runner import ScriptRunner
from app.ui.widgets import LogView, FileDropButton, make_separator
import sys

if getattr(sys, 'frozen', False):
    # BENCH_DIR = Path(sys.executable).parent / "benchmark"
    BENCH_DIR = Path.home() / ".any2notes" / "benchmark"
    BENCH_DIR.parent.mkdir(parents=True, exist_ok=True)
else:
    BENCH_DIR = Path(__file__).parent.parent.parent / "benchmark"


BENCH_FILE = BENCH_DIR / "results.json"


def _load_results() -> list[dict]:
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    if BENCH_FILE.exists():
        try:
            return json.loads(BENCH_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_results(results: list[dict]):
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    BENCH_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))


def _fmt_seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    return f"{int(s//60)}m {s%60:.0f}s"


def _estimate(audio_minutes: float, bench_seconds: float) -> str:
    """Stima tempo per audio_minutes dato che 1 min → bench_seconds."""
    est = audio_minutes * bench_seconds
    return _fmt_seconds(est)


class BenchmarkPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._runner = ScriptRunner(self)
        self._start_time: float = 0.0
        self._results: list[dict] = _load_results()
        self._pending: dict = {}
        self._runner.stdout_line.connect(lambda l: self._log.append_stdout(l))
        self._runner.stderr_line.connect(lambda l: self._log.append_stderr(l))
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(lambda e: self._log.append_stderr(f"ERRORE: {e}"))
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("Benchmark trascrizione")
        title.setObjectName("label_title")
        root.addWidget(title)
        root.addWidget(QLabel(
            "Esegui un test con un file audio di ~1 minuto per stimare i tempi sul tuo hardware."
        ).setObjectName("label_muted") or QLabel(
            "Esegui un test con un file audio di ~1 minuto per stimare i tempi sul tuo hardware."
        ))
        root.addWidget(make_separator())

        # Setup test
        setup_card = QWidget()
        setup_card.setObjectName("card")
        sl = QVBoxLayout(setup_card)
        sl.setSpacing(12)
        sl.addWidget(self._make_section_label("File di test (~1 minuto di audio)"))

        self._file_btn = FileDropButton(
            "Trascina file audio o clicca per sfogliare",
            "Audio (*.mp3 *.wav *.m4a *.ogg *.flac)"
        )
        sl.addWidget(self._file_btn)

        row_params = QHBoxLayout()
        row_params.setSpacing(16)

        col_engine = QVBoxLayout()
        col_engine.addWidget(QLabel("Engine:"))
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["faster-whisper (CPU)", "whisper (CUDA)"])
        col_engine.addWidget(self._engine_combo)

        col_model = QVBoxLayout()
        col_model.addWidget(QLabel("Modello:"))
        self._model_combo = QComboBox()
        self._model_combo.addItems(["turbo", "large-v3"])
        col_model.addWidget(self._model_combo)

        row_params.addLayout(col_engine)
        row_params.addLayout(col_model)
        row_params.addStretch()
        sl.addLayout(row_params)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        sl.addWidget(self._progress)

        btn_row = QHBoxLayout()
        self._btn_run = QPushButton("Avvia benchmark")
        self._btn_run.setObjectName("btn_primary")
        self._btn_run.clicked.connect(self._run_benchmark)
        self._btn_stop = QPushButton("Interrompi")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._runner.stop)
        btn_row.addWidget(self._btn_run)
        btn_row.addWidget(self._btn_stop)
        btn_row.addStretch()
        sl.addLayout(btn_row)
        root.addWidget(setup_card)

        # Log
        log_card = QWidget()
        log_card.setObjectName("card")
        ll = QVBoxLayout(log_card)
        ll.addWidget(self._make_section_label("Output"))
        self._log = LogView()
        self._log.setMinimumHeight(80)
        self._log.setMaximumHeight(120)
        ll.addWidget(self._log)
        root.addWidget(log_card)

        # Risultati
        res_card = QWidget()
        res_card.setObjectName("card")
        rl = QVBoxLayout(res_card)

        res_header = QHBoxLayout()
        res_header.addWidget(self._make_section_label("Storico risultati"))
        self._btn_clear = QPushButton("Cancella storico")
        self._btn_clear.setObjectName("btn_danger")
        self._btn_clear.clicked.connect(self._clear_results)
        res_header.addStretch()
        res_header.addWidget(self._btn_clear)
        rl.addLayout(res_header)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Data", "Engine", "Modello", "Durata test", "Stima 10 min", "Stima 60 min"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.setStyleSheet("""
            QTableWidget {
                background: #1e231d;
                border: none;
                color: #dde8d5;
                gridline-color: #2e352d;
                font-size: 12px;
            }
            QHeaderView::section {
                background: #252b24;
                color: #5a6d54;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                border: none;
                border-bottom: 1px solid #2e352d;
                padding: 6px 8px;
            }
            QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #252b24; }
            QTableWidget::item:selected { background: rgba(122,182,72,0.15); color: #dde8d5; }
        """)
        rl.addWidget(self._table)

        # Suggerimento
        self._suggestion_label = QLabel("")
        self._suggestion_label.setObjectName("label_accent")
        self._suggestion_label.setWordWrap(True)
        rl.addWidget(self._suggestion_label)

        root.addWidget(res_card)
        root.addStretch()

    def _make_section_label(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("label_section")
        return l

    def _run_benchmark(self):
        if not self._file_btn.path:
            QMessageBox.warning(self, "File mancante", "Seleziona un file audio di ~1 minuto.")
            return

        engine_idx = self._engine_combo.currentIndex()
        model = self._model_combo.currentText()

        BENCH_DIR.mkdir(parents=True, exist_ok=True)
        out_file = BENCH_DIR / "bench_output.txt"

        if engine_idx == 0:
            script = "benchmark_whisper.py"
            args = [self._file_btn.path, str(out_file), model, "it", "3", "cpu"]
        else:
            script = "benchmark_whisper.py"
            args = [self._file_btn.path, str(out_file), model, "it", "3", "cuda"]

        self._pending = {
            "engine": self._engine_combo.currentText(),
            "model": model,
        }
        self._start_time = time.time()
        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._progress.show()
        self._log.append_info(f"▶ Benchmark avviato — {self._pending['engine']} / {model}…")
        self._runner.run(script, args)

    def _on_finished(self, exit_code: int):
        elapsed = time.time() - self._start_time
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._progress.hide()

        if exit_code != 0:
            self._log.append_stderr(f"✗ Benchmark fallito (codice {exit_code}).")
            return

        result = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "engine": self._pending["engine"],
            "model": self._pending["model"],
            "elapsed_seconds": round(elapsed, 2),
        }
        self._results.append(result)
        _save_results(self._results)
        self._refresh_table()
        self._log.append_info(
            f"✓ Completato in {_fmt_seconds(elapsed)}  "
            f"→  stima 10 min: {_estimate(10, elapsed)}  /  "
            f"stima 60 min: {_estimate(60, elapsed)}"
        )
        self._update_suggestion(elapsed, self._pending["engine"])

    def _update_suggestion(self, bench_sec: float, engine: str):
        s10  = _estimate(10,  bench_sec)
        s60  = _estimate(60,  bench_sec)
        other = "Faster-Whisper (CPU)" if "CUDA" in engine else "Whisper (CUDA)"
        self._suggestion_label.setText(
            f"Con {engine} / {self._pending['model']}:  10 min audio → ~{s10}  ·  60 min audio → ~{s60}.  "
            f"Prova anche {other} per confrontare."
        )

    def _refresh_table(self):
        self._table.setRowCount(0)
        for r in reversed(self._results):
            row = self._table.rowCount()
            self._table.insertRow(row)
            elapsed = r.get("elapsed_seconds", 0)
            self._table.setItem(row, 0, QTableWidgetItem(r.get("ts", "")[:16].replace("T", " ")))
            self._table.setItem(row, 1, QTableWidgetItem(r.get("engine", "")))
            self._table.setItem(row, 2, QTableWidgetItem(r.get("model", "")))
            self._table.setItem(row, 3, QTableWidgetItem(_fmt_seconds(elapsed)))
            self._table.setItem(row, 4, QTableWidgetItem(_estimate(10, elapsed)))
            self._table.setItem(row, 5, QTableWidgetItem(_estimate(60, elapsed)))

    def _clear_results(self):
        mb = QMessageBox.question(
            self, "Conferma", "Cancellare tutti i risultati del benchmark?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if mb == QMessageBox.StandardButton.Yes:
            self._results = []
            _save_results([])
            self._refresh_table()
            self._suggestion_label.setText("")
