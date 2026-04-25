"""
any2notes — RunManager
Gestisce la persistenza delle run, il versionamento degli output e lo stato degli step.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


RUNS_DIR = Path(__file__).parent.parent.parent / "runs"

STEP_IDS = ["step1_transcribe", "step2_summarize", "step3_export"]

STATUS_IDLE    = "idle"
STATUS_RUNNING = "running"
STATUS_DONE    = "done"
STATUS_ERROR   = "error"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class RunManager:
    """Carica, salva e modifica lo stato di una singola run."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.run_dir = RUNS_DIR / run_id
        self.meta_path = self.run_dir / "run.json"
        self._data: dict = {}
        self._load()

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(cls, name: str) -> "RunManager":
        """Crea una nuova run su disco e restituisce il manager."""
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = name.strip().replace(" ", "_")[:32]
        run_id = f"{ts}_{slug}"
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True)
        for step in STEP_IDS:
            (run_dir / step).mkdir()

        data = {
            "id": run_id,
            "name": name,
            "created": _now(),
            "last_modified": _now(),
            "steps": {
                step: {
                    "status": STATUS_IDLE,
                    "versions": [],
                    "selected_version": None,
                }
                for step in STEP_IDS
            },
        }
        meta_path = run_dir / "run.json"
        meta_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return cls(run_id)

    @classmethod
    def list_all(cls) -> list[dict]:
        """Restituisce lista di metadati di tutte le run, ordinate per data decrescente."""
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        runs = []
        for d in sorted(RUNS_DIR.iterdir(), reverse=True):
            meta = d / "run.json"
            if d.is_dir() and meta.exists():
                try:
                    runs.append(json.loads(meta.read_text(encoding="utf-8")))
                except Exception:
                    pass
        return runs

    @classmethod
    def load(cls, run_id: str) -> "RunManager":
        return cls(run_id)

    def reload(self):
        self._load()

    def _load(self):
        if self.meta_path.exists():
            self._data = json.loads(self.meta_path.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def _save(self):
        self._data["last_modified"] = _now()
        self.meta_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False)
        )

    # ------------------------------------------------------------------ #
    #  Properties                                                          #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return self._data.get("name", self.run_id)

    @property
    def created(self) -> str:
        return self._data.get("created", "")

    @property
    def last_modified(self) -> str:
        return self._data.get("last_modified", "")

    def step_data(self, step_id: str) -> dict:
        return self._data["steps"][step_id]

    def step_status(self, step_id: str) -> str:
        return self.step_data(step_id)["status"]

    def step_versions(self, step_id: str) -> list[dict]:
        return self.step_data(step_id)["versions"]

    def selected_version(self, step_id: str) -> Optional[dict]:
        sel = self.step_data(step_id)["selected_version"]
        if sel is None:
            return None
        versions = self.step_versions(step_id)
        return next((v for v in versions if v["v"] == sel), None)

    def selected_output_path(self, step_id: str) -> Optional[Path]:
        v = self.selected_version(step_id)
        if v is None:
            return None
        return self.run_dir / step_id / v["file"]

    # ------------------------------------------------------------------ #
    #  Mutations                                                           #
    # ------------------------------------------------------------------ #

    def rename(self, new_name: str):
        self._data["name"] = new_name
        self._save()

    def set_step_status(self, step_id: str, status: str):
        self._data["steps"][step_id]["status"] = status
        self._save()

    def add_version(
        self,
        step_id: str,
        filename: str,
        params: dict,
        overwrite_version: Optional[int] = None,
    ) -> int:
        """
        Registra una nuova versione di output per uno step.
        Se overwrite_version è specificato, sostituisce quella versione.
        Ritorna il numero di versione assegnato.
        """
        versions = self._data["steps"][step_id]["versions"]

        if overwrite_version is not None:
            for v in versions:
                if v["v"] == overwrite_version:
                    old_file = self.run_dir / step_id / v["file"]
                    v["file"] = filename
                    v["params"] = params
                    v["ts"] = _now()
                    self._data["steps"][step_id]["selected_version"] = overwrite_version
                    self._save()
                    return overwrite_version

        new_v = max((v["v"] for v in versions), default=0) + 1
        versions.append({"v": new_v, "file": filename, "params": params, "ts": _now()})
        self._data["steps"][step_id]["selected_version"] = new_v
        self._save()
        return new_v

    def select_version(self, step_id: str, version_number: int):
        self._data["steps"][step_id]["selected_version"] = version_number
        self._save()

    def delete(self):
        """Elimina la run e tutti i suoi file dal disco."""
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
