"""
any2notes — Entry point
"""

import sys
from pathlib import Path

# Assicura che il root del progetto sia nel path
if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("any2notes")
    app.setOrganizationName("any2notes")

    # Font di sistema (Segoe UI su Windows)
    app.setFont(QFont("Segoe UI", 10))

    # Carica stylesheet
    qss_path = ROOT / "app" / "ui" / "style.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
