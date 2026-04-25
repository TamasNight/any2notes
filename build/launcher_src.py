"""
launcher_src.py
Entry point compilato da PyInstaller → launcher.exe

Responsabilità:
  - Trova la root dell'applicazione (cartella che contiene launcher.exe)
  - Aggiunge app\ e python\Lib\site-packages al sys.path
  - Lancia main.py usando il Python embeddable bundlato
  - Se qualcosa va storto mostra un messagebox human-friendly

NON importa PyQt6 direttamente: usa subprocess per avviare
main.py con il python dell'env embedded, così il launcher.exe
rimane piccolo (~5 MB) e non porta con sé tutte le dipendenze.
"""

import os
import sys
import subprocess
import ctypes
from pathlib import Path


def find_root() -> Path:
    """Trova la cartella root dell'app (dove è launcher.exe)."""
    if getattr(sys, "frozen", False):
        # Eseguibile PyInstaller
        return Path(sys.executable).parent
    # Sviluppo locale
    return Path(__file__).parent


def show_error(title: str, message: str):
    """Mostra un messagebox Win32 senza dipendere da Qt."""
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR


def main():
    root = find_root()
    python_exe = root / "python" / "python.exe"
    main_py = root / "main.py"

    # Fallback: python di sistema (utile in sviluppo)
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    if not main_py.exists():
        show_error(
            "any2notes — Errore avvio",
            f"File main.py non trovato in:\n{root}\n\n"
            "Reinstalla l'applicazione.",
        )
        sys.exit(1)

    env = os.environ.copy()
    # Assicura che il python embedded trovi i suoi pacchetti
    site_packages = root / "python" / "Lib" / "site-packages"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(root) + os.pathsep + str(site_packages) + (
        os.pathsep + existing if existing else ""
    )
    # Evita che il processo figlio usi il PYTHONHOME del sistema
    env.pop("PYTHONHOME", None)

    try:
        result = subprocess.run(
            [str(python_exe), str(main_py)],
            cwd=str(root),
            env=env,
        )
        sys.exit(result.returncode)
    except FileNotFoundError:
        show_error(
            "any2notes — Errore avvio",
            f"Python non trovato:\n{python_exe}\n\n"
            "Reinstalla l'applicazione.",
        )
        sys.exit(1)
    except Exception as exc:
        show_error("any2notes — Errore inatteso", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
