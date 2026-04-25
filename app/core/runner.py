"""
any2notes — ScriptRunner
Lancia script Python come sottoprocessi asincroni tramite QProcess.
Emette segnali per stdout, stderr, completamento ed errore.
"""

from pathlib import Path
from PyQt6.QtCore import QObject, QProcess, pyqtSignal
from app.core import settings as app_settings

import sys
if getattr(sys, 'frozen', False):
    SCRIPTS_DIR = Path(sys.executable).parent / "scripts"
else:
    SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"


def _python() -> str:
    return app_settings.python_executable()


class ScriptRunner(QObject):
    """Wrapper attorno a QProcess per un singolo script."""

    stdout_line = pyqtSignal(str)   # una riga di stdout
    stderr_line = pyqtSignal(str)   # una riga di stderr
    finished    = pyqtSignal(int)   # exit code
    error       = pyqtSignal(str)   # messaggio di errore human-readable

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: QProcess | None = None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def run(self, script_name: str, args: list[str]):
        """Avvia script_name con gli argomenti forniti."""
        if self.is_running():
            self.error.emit("Un processo è già in esecuzione.")
            return

        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            self.error.emit(f"Script non trovato: {script_path}")
            return

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._process.start(_python(), [str(script_path)] + args)

    def stop(self):
        """Termina il processo se in esecuzione."""
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(3000):
                self._process.kill()

    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    # ------------------------------------------------------------------ #
    #  Private slots                                                       #
    # ------------------------------------------------------------------ #

    def _on_stdout(self):
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self.stdout_line.emit(line)

    def _on_stderr(self):
        data = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self.stderr_line.emit(line)

    def _on_finished(self, exit_code: int, _exit_status):
        self.finished.emit(exit_code)

    def _on_error(self, error):
        messages = {
            QProcess.ProcessError.FailedToStart: "Impossibile avviare il processo. Verifica il percorso Python.",
            QProcess.ProcessError.Crashed:       "Il processo è crashato.",
            QProcess.ProcessError.Timedout:      "Timeout.",
            QProcess.ProcessError.WriteError:    "Errore di scrittura.",
            QProcess.ProcessError.ReadError:     "Errore di lettura.",
            QProcess.ProcessError.UnknownError:  "Errore sconosciuto.",
        }
        self.error.emit(messages.get(error, "Errore sconosciuto."))


class PipelineRunner(QObject):
    """
    Esegue più ScriptRunner in sequenza.
    Se uno step fallisce, la pipeline si interrompe.
    """

    step_started  = pyqtSignal(int, str)   # (index, script_name)
    step_stdout   = pyqtSignal(int, str)   # (index, line)
    step_stderr   = pyqtSignal(int, str)   # (index, line)
    step_finished = pyqtSignal(int, int)   # (index, exit_code)
    pipeline_done = pyqtSignal()
    pipeline_error= pyqtSignal(str)

    def __init__(self, steps: list[tuple[str, list[str]]], parent=None):
        """
        steps: lista di (script_name, args)
        """
        super().__init__(parent)
        self._steps = steps
        self._current = 0
        self._runner: ScriptRunner | None = None

    def start(self):
        self._current = 0
        self._run_next()

    def stop(self):
        if self._runner:
            self._runner.stop()

    def _run_next(self):
        if self._current >= len(self._steps):
            self.pipeline_done.emit()
            return

        script_name, args = self._steps[self._current]
        self._runner = ScriptRunner(self)
        idx = self._current

        self._runner.stdout_line.connect(lambda l: self.step_stdout.emit(idx, l))
        self._runner.stderr_line.connect(lambda l: self.step_stderr.emit(idx, l))
        self._runner.error.connect(lambda e: self.pipeline_error.emit(e))
        self._runner.finished.connect(self._on_step_finished)

        self.step_started.emit(idx, script_name)
        self._runner.run(script_name, args)

    def _on_step_finished(self, exit_code: int):
        self.step_finished.emit(self._current, exit_code)
        if exit_code != 0:
            self.pipeline_error.emit(
                f"Step {self._current + 1} terminato con codice {exit_code}."
            )
            return
        self._current += 1
        self._run_next()
