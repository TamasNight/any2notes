"""
any2notes — Widgets riutilizzabili
LogView, VersionSelector, FileDropButton, StatusPill, StepBadge
"""

from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QButtonGroup, QRadioButton, QSizePolicy,
    QFileDialog, QFrame,
)


# ── LogView ───────────────────────────────────────────────────────────── #

class LogView(QPlainTextEdit):
    """Terminale read-only per l'output degli script."""

    MAX_LINES = 2000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("log_view")
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setPlaceholderText("Output del processo…")

    def append_stdout(self, line: str):
        self._append(line, "#7ab648")

    def append_stderr(self, line: str):
        self._append(line, "#c06060")

    def append_info(self, line: str):
        self._append(line, "#5a6d54")

    def _append(self, line: str, color: str):
        self.appendHtml(f'<span style="color:{color};">{line}</span>')
        # Limita le righe per non consumare troppa memoria
        doc = self.document()
        while doc.blockCount() > self.MAX_LINES:
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def clear_log(self):
        self.clear()


# ── VersionSelector ───────────────────────────────────────────────────── #

class VersionSelector(QWidget):
    """
    Mostra le versioni disponibili di uno step e permette di selezionarne una
    o usare un file esterno.
    """

    version_selected = pyqtSignal(int)    # numero versione
    external_file_selected = pyqtSignal(str)  # path file esterno

    def __init__(self, step_label: str, file_filter: str = "Tutti i file (*)", parent=None):
        super().__init__(parent)
        self._file_filter = file_filter
        self._group = QButtonGroup(self)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        header = QLabel(f"Input — {step_label}")
        header.setObjectName("label_section")
        self._layout.addWidget(header)

        self._versions_container = QVBoxLayout()
        self._versions_container.setSpacing(4)
        self._layout.addLayout(self._versions_container)

        # Radio "file esterno"
        self._ext_radio = QRadioButton("Usa file esterno…")
        self._ext_radio.toggled.connect(self._on_external_toggled)
        self._group.addButton(self._ext_radio, -1)
        self._layout.addWidget(self._ext_radio)

        self._ext_path_label = QLabel("")
        self._ext_path_label.setObjectName("label_accent")
        self._ext_path_label.hide()
        self._layout.addWidget(self._ext_path_label)

        self._ext_btn = QPushButton("Sfoglia…")
        self._ext_btn.setObjectName("btn_ghost")
        self._ext_btn.hide()
        self._ext_btn.clicked.connect(self._browse_external)
        self._layout.addWidget(self._ext_btn)

    def set_versions(self, versions: list[dict], selected_v: int | None):
        """Popola i radio button con le versioni fornite dal RunManager."""
        # Pulisci precedenti
        while self._versions_container.count():
            item = self._versions_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Rimuovi vecchi button dal gruppo
        for btn in self._group.buttons():
            if btn is not self._ext_radio:
                self._group.removeButton(btn)

        for v in versions:
            ts = v.get("ts", "")[:16].replace("T", " ")
            params = v.get("params", {})
            param_str = "  ·  ".join(f"{k}: {val}" for k, val in params.items())
            label = f"v{v['v']}  ·  {ts}  ·  {param_str}"
            rb = QRadioButton(label)
            rb.setStyleSheet("color: #8fa882; font-size: 12px;")
            self._group.addButton(rb, v["v"])
            rb.toggled.connect(
                lambda checked, vn=v["v"]: self.version_selected.emit(vn) if checked else None
            )
            self._versions_container.addWidget(rb)
            if v["v"] == selected_v:
                rb.setChecked(True)

        if not versions:
            placeholder = QLabel("Nessun output disponibile dallo step precedente")
            placeholder.setObjectName("label_muted")
            self._versions_container.addWidget(placeholder)
            self._ext_radio.setChecked(True)

    def _on_external_toggled(self, checked: bool):
        self._ext_btn.setVisible(checked)
        if not checked:
            self._ext_path_label.hide()

    def _browse_external(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona file", "", self._file_filter)
        if path:
            self._ext_path_label.setText(Path(path).name)
            self._ext_path_label.show()
            self.external_file_selected.emit(path)


# ── FileDropButton ────────────────────────────────────────────────────── #

class FileDropButton(QPushButton):
    """
    Pulsante drag-and-drop + click per selezionare un file.
    Emette file_selected(path).
    """

    file_selected = pyqtSignal(str)

    def __init__(self, label: str = "Trascina file o clicca per sfogliare",
                 file_filter: str = "Tutti i file (*)", parent=None):
        super().__init__(label, parent)
        self._filter = file_filter
        self._path: str | None = None
        self.setAcceptDrops(True)
        self.setMinimumHeight(56)
        self.setStyleSheet("""
            QPushButton {
                border: 1px dashed #3a4838;
                border-radius: 8px;
                color: #5a6d54;
                font-size: 12px;
                padding: 12px;
            }
            QPushButton:hover {
                border-color: #7ab648;
                color: #8fa882;
                background-color: rgba(122,182,72,0.07);
            }
        """)
        self.clicked.connect(self._browse)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona file", "", self._filter)
        if path:
            self._set_path(path)

    def _set_path(self, path: str):
        self._path = path
        self.setText(Path(path).name)
        self.setStyleSheet(self.styleSheet() + "QPushButton { color: #7ab648; }")
        self.file_selected.emit(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            self._set_path(urls[0].toLocalFile())

    @property
    def path(self) -> str | None:
        return self._path


# ── StatusPill ────────────────────────────────────────────────────────── #

class StatusPill(QLabel):
    """Pillola colorata per lo stato di Ollama o di uno step."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._set_style("#252b24", "#4d6349", "#5a6d54")

    def set_ok(self, text: str):
        self.setText(text)
        self._set_style("rgba(122,182,72,0.13)", "#5d9130", "#7ab648")

    def set_warning(self, text: str):
        self.setText(text)
        self._set_style("rgba(200,150,50,0.13)", "#8a6020", "#c89040")

    def set_error(self, text: str):
        self.setText(text)
        self._set_style("rgba(192,96,96,0.13)", "#7a3030", "#c06060")

    def _set_style(self, bg: str, border: str, color: str):
        self.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 99px;
                color: {color};
                font-size: 11px;
                padding: 3px 10px;
            }}
        """)


# ── StepBadge ─────────────────────────────────────────────────────────── #

class StepBadge(QLabel):
    """Numero o checkmark circolare accanto ai nav item."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_idle(text)

    def set_idle(self, text: str):
        self.setText(text)
        self.setStyleSheet("""
            QLabel {
                background: rgba(122,182,72,0.10);
                color: #5a6d54;
                border-radius: 10px;
                font-size: 10px;
                font-weight: 600;
            }
        """)

    def set_active(self, text: str):
        self.setText(text)
        self.setStyleSheet("""
            QLabel {
                background: rgba(122,182,72,0.22);
                color: #7ab648;
                border-radius: 10px;
                font-size: 10px;
                font-weight: 600;
            }
        """)

    def set_done(self):
        self.setText("✓")
        self.setStyleSheet("""
            QLabel {
                background: #7ab648;
                color: #0f1a0a;
                border-radius: 10px;
                font-size: 10px;
                font-weight: 700;
            }
        """)


# ── Separator ─────────────────────────────────────────────────────────── #

def make_separator() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet("border-top: 1px solid #2e352d;")
    return sep
