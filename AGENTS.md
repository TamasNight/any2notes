# any2notes — Agent Instructions

## Run
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Architecture
- `main.py` → PyQt6 QApplication → `MainWindow`
- `app/core/` — logic layer: `run_manager.py` (run CRUD + versioning), `runner.py` (QProcess wrappers: `ScriptRunner`, `PipelineRunner`), `settings.py` (global config), `ollama_service.py` (async Ollama health check via QThread)
- `app/ui/` — `main_window.py` (sidebar + nav + run list), `step_panels.py` (3 step panels), `widgets.py`, `style.qss`
- `scripts/` — standalone Python scripts invoked as subprocesses by runner.py

Pipeline: `scripts/speech2text.py` (or `fast-speech2text.py`) → `scripts/summary.py` / `summarize_lecture.py` → `scripts/md2doc.py`

## Critical gotchas
- **Frozen vs dev paths**: All modules use `getattr(sys, 'frozen', False)` to resolve roots. When frozen (launcher.exe), `RUNS_DIR` goes to `~/.any2notes`, `SETTINGS_FILE` to `~/.any2notes/settings.json`. In dev, both are project-local. **Never hardcode relative paths from `__file__` without checking `sys.frozen`.**
- **Ollama is required** for step 2. It must be running (`ollama serve`) with a model pulled (gemma4, qwen3.6, or minimax-m2.7:cloud).
- **Pandoc is required** for step 3. Must be in system PATH (dev) or bundled in `build\bin\pandoc.exe` (release).
- **No tests, no lint, no typecheck, no formatter.** This is a personal project — skip those steps.
- `settings.json` is git-ignored and generated at first run. Do not commit it.
- `runs/`, `benchmark/`, `models/`, `build/`, `dist/` are all generated and git-ignored.

## Build (release)
```bat
build\build_env.bat          # Prepares python_env\ + compiles launcher.exe
# Then open installer\any2notes.iss with Inno Setup Compiler and press F9
# Output: dist\any2notes-setup-0.4.1.exe
```

Prerequisites for build: PyInstaller (`pip install pyinstaller`), Inno Setup 6.x, pandoc.exe placed in `build\bin\`.

## Run versioning
Each run creates a timestamped directory under `runs/` with 3 step subdirectories. Each step supports multiple versions (`output_v1.txt`, `output_v2.txt`, ...). Re-running a step prompts: overwrite last version or create new version.
