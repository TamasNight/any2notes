"""
any2notes — OllamaService
Verifica la disponibilità di Ollama e recupera i modelli installati.
Tutto asincrono tramite QThread per non bloccare la UI.
"""

import json
import urllib.request
import urllib.error
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from app.core import settings as app_settings


def _get(path: str, timeout: float = 3.0) -> dict | list | None:
    base = app_settings.ollama_host()
    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


class OllamaChecker(QObject):
    """
    Controlla in background se Ollama è attivo e quali modelli sono disponibili.
    Usare tramite QThread oppure chiamate dirette (bloccanti) a seconda del contesto.
    """

    result = pyqtSignal(bool, list)   # (is_running, model_names)

    def check(self):
        """Chiamata bloccante — eseguire in un thread separato."""
        data = _get("/api/tags")
        if data is None:
            self.result.emit(False, [])
            return
        models = [m["name"] for m in data.get("models", [])]
        self.result.emit(True, models)


class OllamaService(QObject):
    """
    Servizio di alto livello: avvia un check periodico e notifica la UI.
    """

    status_changed = pyqtSignal(bool, list)   # (running, models)

    # modelli online noti (aggiungi secondo necessità)
    KNOWN_ONLINE = ["minimax-m2.7:cloud"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._models: list[str] = []
        self._thread: QThread | None = None
        self._checker: OllamaChecker | None = None

    def refresh(self):
        """Avvia un check asincrono. Emette status_changed al termine."""
        if self._thread and self._thread.isRunning():
            return

        self._thread = QThread(self)
        self._checker = OllamaChecker()
        self._checker.moveToThread(self._thread)
        self._checker.result.connect(self._on_result)
        self._thread.started.connect(self._checker.check)
        self._thread.start()

    def _on_result(self, running: bool, models: list[str]):
        self._running = running
        self._models = models
        self.status_changed.emit(running, models)
        self._thread.quit()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def local_models(self) -> list[str]:
        return [m for m in self._models if m not in self.KNOWN_ONLINE]

    @property
    def all_models(self) -> list[str]:
        return self._models + [m for m in self.KNOWN_ONLINE if m not in self._models]
