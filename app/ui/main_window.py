"""
any2notes — MainWindow
Finestra principale: sidebar con gestione run, pipeline bar, pannelli step.
"""

from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QScrollArea, QFrame, QInputDialog,
    QMessageBox, QStackedWidget, QSizePolicy,
)

from app.core.run_manager import RunManager, STATUS_DONE, STATUS_IDLE, STATUS_RUNNING, STATUS_ERROR, STEP_IDS
from app.core.ollama_service import OllamaService
from app.ui.widgets import StatusPill, StepBadge, make_separator
from app.ui.step_panels import Step1Panel, Step2Panel, Step3Panel
from app.ui.benchmark_panel import BenchmarkPanel
from app.ui.settings_panel import SettingsPanel


# ── Pipeline step definitions ─────────────────────────────────────────── #

STEPS = [
    {"id": "step1_transcribe", "label": "Trascrizione",   "icon": "🎙"},
    {"id": "step2_summarize",  "label": "Riassunto",      "icon": "📝"},
    {"id": "step3_export",     "label": "Esporta doc",    "icon": "📄"},
]

STATUS_COLORS = {
    STATUS_IDLE:    "#5a6d54",
    STATUS_RUNNING: "#c89040",
    STATUS_DONE:    "#7ab648",
    STATUS_ERROR:   "#c06060",
}


# ── NavButton ─────────────────────────────────────────────────────────── #

class NavButton(QPushButton):
    def __init__(self, label: str, badge_text: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("nav_btn")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(36)
        self.setCheckable(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(8)

        self._label = QLabel(label)
        self._label.setStyleSheet("font-size: 13px; background: transparent;")
        layout.addWidget(self._label)
        layout.addStretch()

        self._badge = StepBadge(badge_text)
        layout.addWidget(self._badge)

    def set_active(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.setChecked(active)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_badge_done(self):
        self._badge.set_done()

    def set_badge_idle(self, text: str):
        self._badge.set_idle(text)

    def set_badge_active(self, text: str):
        self._badge.set_active(text)


# ── RunListItem ───────────────────────────────────────────────────────── #

class RunListItem(QWidget):
    """Riga nella lista run della sidebar."""

    selected = pyqtSignal(str)   # run_id
    deleted  = pyqtSignal(str)

    def __init__(self, run_data: dict, is_active: bool = False, parent=None):
        super().__init__(parent)
        self._run_id = run_data["id"]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)
        layout.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {'#7ab648' if is_active else '#3a4838'}; font-size: 9px;")
        layout.addWidget(dot)

        info = QVBoxLayout()
        name = QLabel(run_data.get("name", run_data["id"]))
        name.setStyleSheet("font-size: 12px; color: #dde8d5;" if is_active else "font-size: 12px; color: #8fa882;")
        steps_done = sum(
            1 for s in run_data.get("steps", {}).values()
            if s.get("status") == STATUS_DONE
        )
        progress = QLabel(f"{steps_done}/3 step")
        progress.setStyleSheet("font-size: 10px; color: #5a6d54;")
        info.addWidget(name)
        info.addWidget(progress)
        layout.addLayout(info)
        layout.addStretch()

        del_btn = QPushButton("✕")
        del_btn.setObjectName("btn_icon")
        del_btn.setFixedSize(22, 22)
        del_btn.clicked.connect(lambda: self.deleted.emit(self._run_id))
        layout.addWidget(del_btn)

        self.setStyleSheet(
            "QWidget { background: rgba(122,182,72,0.08); border-left: 2px solid #7ab648; }"
            if is_active else
            "QWidget { background: transparent; border-left: 2px solid transparent; }"
            "QWidget:hover { background: rgba(122,182,72,0.05); }"
        )
        self.mousePressEvent = lambda e: self.selected.emit(self._run_id)


# ── PipelineBar ───────────────────────────────────────────────────────── #

class PipelineBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pipeline_bar")
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        self._step_labels = []
        for i, step in enumerate(STEPS):
            dot = QLabel("●")
            dot.setObjectName(f"pipe_dot_{i}")
            dot.setStyleSheet("font-size: 8px; color: #3a4838;")
            lbl = QLabel(step["label"])
            lbl.setStyleSheet("font-size: 12px; color: #5a6d54; margin-left: 6px;")
            self._step_labels.append((dot, lbl))
            layout.addWidget(dot)
            layout.addWidget(lbl)
            if i < len(STEPS) - 1:
                arr = QLabel("→")
                arr.setStyleSheet("color: #3a4838; margin: 0 12px; font-size: 12px;")
                layout.addWidget(arr)
        layout.addStretch()

    def update_statuses(self, run: RunManager):
        for i, step in enumerate(STEPS):
            status = run.step_status(step["id"])
            dot, lbl = self._step_labels[i]
            color = STATUS_COLORS.get(status, "#3a4838")
            dot.setStyleSheet(f"font-size: 8px; color: {color};")
            text_color = color if status != STATUS_IDLE else "#5a6d54"
            weight = "font-weight: 500;" if status == STATUS_RUNNING else ""
            lbl.setStyleSheet(f"font-size: 12px; color: {text_color}; margin-left: 6px; {weight}")


# ── MainWindow ────────────────────────────────────────────────────────── #

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("any2notes")
        self.resize(1100, 740)
        self.setMinimumSize(800, 560)

        self._current_run: RunManager | None = None
        self._ollama = OllamaService(self)
        self._ollama.status_changed.connect(self._on_ollama_status)

        self._build_ui()
        self._load_runs_list()

        # Check Ollama all'avvio
        QTimer.singleShot(500, self._ollama.refresh)
        # Re-check ogni 30s
        self._ollama_timer = QTimer(self)
        self._ollama_timer.timeout.connect(self._ollama.refresh)
        self._ollama_timer.start(30_000)

    # ------------------------------------------------------------------ #
    #  Build UI                                                            #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ── #
        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(210)
        sb_layout = QVBoxLayout(self._sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # App name
        app_name = QLabel("any2notes")
        app_name.setStyleSheet(
            "font-size: 15px; font-weight: 600; color: #7ab648; "
            "padding: 18px 16px 12px 16px; letter-spacing: 0.04em;"
        )
        sb_layout.addWidget(app_name)

        # Ollama status
        self._ollama_pill = StatusPill("Ollama…")
        self._ollama_pill.setStyleSheet(
            self._ollama_pill.styleSheet() + "QLabel { margin: 0 12px 10px 12px; }"
        )
        sb_layout.addWidget(self._ollama_pill)
        sb_layout.addWidget(make_separator())

        # Pipeline nav
        pipeline_section = QLabel("PIPELINE")
        pipeline_section.setObjectName("sidebar_section_label")
        sb_layout.addWidget(pipeline_section)

        self._nav_buttons: list[NavButton] = []
        panel_indices = {0: 0, 1: 1, 2: 2}  # nav_idx → stack_idx
        for i, step in enumerate(STEPS):
            btn = NavButton(step["label"], str(i + 1))
            btn.clicked.connect(lambda _, idx=i: self._navigate_to(idx))
            self._nav_buttons.append(btn)
            sb_layout.addWidget(btn)

        sb_layout.addWidget(make_separator())

        # Tools
        tools_section = QLabel("STRUMENTI")
        tools_section.setObjectName("sidebar_section_label")
        sb_layout.addWidget(tools_section)

        self._bench_btn = NavButton("Benchmark", "◎")
        self._bench_btn.clicked.connect(lambda: self._navigate_to(3))
        sb_layout.addWidget(self._bench_btn)

        self._settings_btn = NavButton("Impostazioni", "⚙")
        self._settings_btn.clicked.connect(lambda: self._navigate_to(4))
        sb_layout.addWidget(self._settings_btn)

        sb_layout.addWidget(make_separator())

        # Run list
        runs_header = QHBoxLayout()
        runs_header.setContentsMargins(14, 8, 10, 4)
        runs_lbl = QLabel("RUN")
        runs_lbl.setObjectName("sidebar_section_label")
        runs_header.addWidget(runs_lbl)
        runs_header.addStretch()
        new_run_btn = QPushButton("+")
        new_run_btn.setObjectName("btn_icon")
        new_run_btn.setFixedSize(22, 22)
        new_run_btn.setToolTip("Nuova run")
        new_run_btn.clicked.connect(self._create_run)
        runs_header.addWidget(new_run_btn)
        sb_layout.addLayout(runs_header)

        self._runs_scroll = QScrollArea()
        self._runs_scroll.setWidgetResizable(True)
        self._runs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._runs_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._runs_container = QWidget()
        self._runs_container.setStyleSheet("background: transparent;")
        self._runs_list_layout = QVBoxLayout(self._runs_container)
        self._runs_list_layout.setContentsMargins(0, 0, 0, 0)
        self._runs_list_layout.setSpacing(0)
        self._runs_list_layout.addStretch()
        self._runs_scroll.setWidget(self._runs_container)
        sb_layout.addWidget(self._runs_scroll)

        # ── Main area ── #
        main_area = QWidget()
        main_area.setObjectName("main_area")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Pipeline bar
        self._pipeline_bar = PipelineBar()
        self._pipeline_bar.setVisible(False)
        main_layout.addWidget(self._pipeline_bar)

        sep = make_separator()
        main_layout.addWidget(sep)

        # No-run placeholder
        self._no_run_widget = QWidget()
        nr_layout = QVBoxLayout(self._no_run_widget)
        nr_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nr_lbl = QLabel("Nessuna run attiva.\nClicca + per crearne una nuova.")
        nr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nr_lbl.setObjectName("label_muted")
        nr_lbl.setStyleSheet("font-size: 14px; color: #3a4838; line-height: 1.8;")
        nr_layout.addWidget(nr_lbl)
        nr_btn = QPushButton("+ Nuova run")
        nr_btn.setObjectName("btn_primary")
        nr_btn.setFixedWidth(160)
        nr_btn.clicked.connect(self._create_run)
        nr_layout.addWidget(nr_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._no_run_widget)

        # Stacked panels
        self._stack = QStackedWidget()
        self._stack.setVisible(False)

        self._panel_step1 = Step1Panel(self._ollama)
        self._panel_step2 = Step2Panel(self._ollama)
        self._panel_step3 = Step3Panel(self._ollama)
        self._panel_bench = BenchmarkPanel()
        self._panel_settings = SettingsPanel()

        # Connect step completion signals
        self._panel_step1.step_completed.connect(lambda: self._on_step_completed(0))
        self._panel_step2.step_completed.connect(lambda: self._on_step_completed(1))
        self._panel_step3.step_completed.connect(lambda: self._on_step_completed(2))

        scroll1 = self._scrollable(self._panel_step1)
        scroll2 = self._scrollable(self._panel_step2)
        scroll3 = self._scrollable(self._panel_step3)
        scroll4 = self._scrollable(self._panel_bench)
        scroll5 = self._scrollable(self._panel_settings)

        self._stack.addWidget(scroll1)
        self._stack.addWidget(scroll2)
        self._stack.addWidget(scroll3)
        self._stack.addWidget(scroll4)
        self._stack.addWidget(scroll5)

        main_layout.addWidget(self._stack)

        # Status bar
        self._status_bar_lbl = QLabel("Pronto")
        self.statusBar().addWidget(self._status_bar_lbl)
        self._model_lbl = QLabel("")
        self.statusBar().addPermanentWidget(self._model_lbl)

        root.addWidget(self._sidebar)
        root.addWidget(main_area)

    def _scrollable(self, widget: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(widget)
        sa.setStyleSheet("QScrollArea { border: none; }")
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return sa

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def _navigate_to(self, index: int):
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == index)
        self._bench_btn.set_active(index == 3)
        self._settings_btn.set_active(index == 4)
        self._stack.setCurrentIndex(index)

    def _on_step_completed(self, step_index: int):
        if self._current_run:
            self._update_badges()
            self._pipeline_bar.update_statuses(self._current_run)
        # Suggerisci prossimo step
        if step_index < 2:
            self._navigate_to(step_index + 1)

    def _update_badges(self):
        if not self._current_run:
            return
        for i, step in enumerate(STEPS):
            status = self._current_run.step_status(step["id"])
            btn = self._nav_buttons[i]
            if status == STATUS_DONE:
                btn.set_badge_done()
            elif status == STATUS_RUNNING:
                btn.set_badge_active("▶")
            else:
                btn.set_badge_idle(str(i + 1))

    # ------------------------------------------------------------------ #
    #  Run management                                                      #
    # ------------------------------------------------------------------ #

    def _create_run(self):
        name, ok = QInputDialog.getText(self, "Nuova run", "Nome della run:")
        if not ok or not name.strip():
            return
        run = RunManager.create(name.strip())
        self._current_run = run
        self._load_runs_list()
        self._activate_run(run)

    def _activate_run(self, run: RunManager):
        self._current_run = run
        self._pipeline_bar.setVisible(True)
        self._pipeline_bar.update_statuses(run)
        self._no_run_widget.setVisible(False)
        self._stack.setVisible(True)
        self._panel_step1.set_run(run)
        self._panel_step2.set_run(run)
        self._panel_step3.set_run(run)
        self._update_badges()
        self._navigate_to(0)
        self._status_bar_lbl.setText(f"Run: {run.name}")
        self._load_runs_list()

    def _load_runs_list(self):
        # Pulisci lista
        while self._runs_list_layout.count() > 1:
            item = self._runs_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        runs = RunManager.list_all()
        current_id = self._current_run.run_id if self._current_run else None

        for run_data in runs:
            is_active = run_data["id"] == current_id
            item = RunListItem(run_data, is_active)
            item.selected.connect(self._on_run_selected)
            item.deleted.connect(self._on_run_deleted)
            self._runs_list_layout.insertWidget(self._runs_list_layout.count() - 1, item)

        if not runs:
            placeholder = QLabel("Nessuna run")
            placeholder.setStyleSheet("color: #3a4838; font-size: 11px; padding: 8px 14px;")
            self._runs_list_layout.insertWidget(0, placeholder)

    def _on_run_selected(self, run_id: str):
        run = RunManager.load(run_id)
        self._activate_run(run)

    def _on_run_deleted(self, run_id: str):
        mb = QMessageBox.question(
            self, "Elimina run",
            "Eliminare questa run e tutti i suoi file?\nL'operazione non è reversibile.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if mb == QMessageBox.StandardButton.Yes:
            run = RunManager.load(run_id)
            run.delete()
            if self._current_run and self._current_run.run_id == run_id:
                self._current_run = None
                self._pipeline_bar.setVisible(False)
                self._stack.setVisible(False)
                self._no_run_widget.setVisible(True)
                self._status_bar_lbl.setText("Pronto")
            self._load_runs_list()

    # ------------------------------------------------------------------ #
    #  Ollama                                                              #
    # ------------------------------------------------------------------ #

    def _on_ollama_status(self, running: bool, models: list):
        if running:
            self._ollama_pill.set_ok(f"Ollama ✓  ({len(models)} modelli)")
            model_names = ", ".join(models[:3])
            if len(models) > 3:
                model_names += f" +{len(models)-3}"
            self._model_lbl.setText(model_names)
        else:
            self._ollama_pill.set_error("Ollama non trovato")
            self._model_lbl.setText("")
            self.statusBar().showMessage(
                "⚠ Ollama non in esecuzione — avvialo o scaricalo da ollama.com", 8000
            )
