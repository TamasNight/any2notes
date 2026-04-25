"""
any2notes — app/core/settings.py
Accesso globale alle impostazioni da qualsiasi modulo.
Evita di importare SettingsPanel (UI) dal layer core.
"""

from pathlib import Path
import json
import sys

if getattr(sys, 'frozen', False):
    SETTINGS_FILE = Path(sys.executable).parent / "settings.json"
else:
    SETTINGS_FILE = Path(__file__).parent.parent.parent / "settings.json"

DEFAULTS = {
    "python_path": "",
    "pandoc_path": "",
    "default_model_whisper": "turbo",
    "default_language": "it",
    "default_beam_size": 3,
    "default_ollama_model": "gemma4",
    "default_chunk_size": 4000,
    "cuda_available": False,
    "ollama_host": "http://localhost:11434",
}

_cache: dict | None = None


def get() -> dict:
    global _cache
    if _cache is None:
        reload()
    return _cache


def reload():
    global _cache
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            _cache = {**DEFAULTS, **data}
            return
        except Exception:
            pass
    _cache = dict(DEFAULTS)


def python_executable() -> str:
    """Ritorna il path Python da usare per lanciare gli script."""
    # Python embeddable accanto al launcher
    cfg = get().get("python_path", "").strip()
    if cfg and Path(cfg).exists():
        return cfg

    import sys
    if getattr(sys, 'frozen', False):
        embedded = Path(sys.executable).parent / "python" / "python.exe"
        if embedded.exists():
            return str(embedded)

    return sys.executable


def pandoc_executable() -> str:
    """Ritorna il path di pandoc."""
    cfg = get().get("pandoc_path", "").strip()
    if cfg and Path(cfg).exists():
        return cfg
    return "pandoc"  # si fida del PATH di sistema


def ollama_host() -> str:
    return get().get("ollama_host", DEFAULTS["ollama_host"])
