# any2notes

Applicazione desktop Windows per automatizzare il workflow:
**audio → trascrizione → riassunto → documento**.

Wrapper UI (PyQt6) per una pipeline di script Python:
`speech2text` → `summary / summarize_lecture` → `md2doc`

---

## Struttura del progetto

```
any2notes/
├── main.py                     # Entry point
├── requirements.txt            
├── settings.json               # Generato al primo avvio
│
├── app/
│   ├── core/
│   │   ├── run_manager.py      # Persistenza run e versionamento
│   │   ├── runner.py           # QProcess wrapper per gli script
│   │   ├── ollama_service.py   # Check Ollama asincrono
│   │   └── settings.py        # Configurazione globale
│   └── ui/
│       ├── main_window.py      # Finestra principale + sidebar
│       ├── step_panels.py      # Pannelli step 1/2/3
│       ├── benchmark_panel.py  # Benchmark velocità Whisper
│       ├── settings_panel.py   # Pannello impostazioni
│       ├── widgets.py          # Widget riutilizzabili
│       └── style.qss           # Tema dark botanico
│
├── scripts/                    # I tuoi script Python
│   ├── speech2text.py
│   ├── fast-speech2text.py
│   ├── summary.py
│   ├── summarize_lecture.py
│   ├── md2doc.py
│   └── benchmark_whisper.py   # Generato — non modificare
│
├── runs/                       # Dati persistenti delle run (auto-creata)
│   └── <timestamp>_<nome>/
│       ├── run.json
│       ├── step1_transcribe/
│       ├── step2_summarize/
│       └── step3_export/
│
├── benchmark/                  # Risultati benchmark (auto-creata)
│   └── results.json
│
├── models/                     # Cache modelli Whisper (auto-creata)
│
├── build/
│   ├── build_env.bat           # Script di build completo
│   ├── launcher_src.py         # Sorgente del launcher.exe
│   └── bin/
│       └── pandoc.exe          # Da aggiungere manualmente
│
└── installer/
    └── any2notes.iss           # Script Inno Setup
```

---

## Sviluppo locale

### Prerequisiti

- Python 3.11+
- pip

### Setup ambiente

```bash
# Clona il repo e spostati nella root
cd any2notes

# Crea e attiva un venv
python -m venv .venv
.venv\Scripts\activate       # Windows

# Installa le dipendenze degli script (vedi sezione sotto)
pip install -r requirements.txt
```

### Avvio in sviluppo

```bash
python main.py
```

Lo script `runner.py` userà automaticamente il Python del venv corrente
se non trova `python\python.exe` nella root del progetto.

### Dipendenze degli script

| Script | Librerie pip                                                                             |
|---|------------------------------------------------------------------------------------------|
| `fast-speech2text.py` | `faster-whisper`                                                                         |
| `speech2text.py` | `openai-whisper`, `torch` (CUDA)                                                         |
| `summary.py` | `ollama`, ollama (eseguibile esterno)                                                    |
| `summarize_lecture.py` | `ollama`, `python-pptx`, `Pillow`, `pdfplumber`, `pypdf` , ollama (eseguibile esterno)   |
| `md2doc.py` | `pypadoc`, pandoc (eseguibile esterno)                                                   |

### Pandoc

Scarica pandoc da [pandoc.org](https://pandoc.org/installing.html).

In sviluppo basta che sia nel PATH di sistema.
In distribuzione viene bundlato in `build\bin\pandoc.exe`.

### Ollama

Scarica e installa da [ollama.com](https://ollama.com/download).

Prima di avviare any2notes:
```bash
ollama serve
# In un altro terminale:
ollama pull gemma4
# o il modello che preferisci:
ollama pull any
```

---

## Build per distribuzione (Windows)

### 1. Prepara l'ambiente

```bat
cd build
build_env.bat
```

Questo script:
- Scarica Python 3.11 Embeddable in `build\python_env\`
- Installa pip
- Compila `launcher.exe` con PyInstaller in `build\output\`

### 2. Compila l'installer

Apri `installer\any2notes.iss` con **Inno Setup Compiler** e premi F9.

L'installer finale viene generato in:
```
dist\any2notes-setup-0.4.1.exe
```

### Cosa installa l'installer

- `launcher.exe` — avvia l'app
- `app\` — codice UI PyQt6
- `scripts\` — script Python
- `python\` — Python 3.11 embeddable con tutte le dipendenze
- Dipendenza Python nell'embed usando pip
- Shortcut desktop e menu Start
- Check Ollama: se non trovato, mostra messaggio con link al download

---

## Gestione Run

Ogni sessione di lavoro è una **run** persistente su disco. I file di output e configurazione vengono salvati nella cartella `~/.any2notes`:

```
runs/
└── 20250424_143201_lezione01/
    ├── run.json                  ← stato, parametri, versioni
    ├── step1_transcribe/
    │   ├── output_v1.txt         ← trascrizione con turbo
    │   └── output_v2.txt         ← rifatta con large-v3
    ├── step2_summarize/
    │   └── output_v1.md
    └── step3_export/
        └── output_v1.docx
```

**Funzionalità:**
- Più run attive in parallelo, navigabili dalla sidebar
- Ogni step può essere rieseguito: scegli se sovrascrivere o creare una nuova versione
- Nello step successivo puoi scegliere quale versione dell'output precedente usare
- Export singolo file in qualsiasi momento
- Eliminazione run con conferma

---

## Benchmark

La sezione **Benchmark** permette di:

1. Eseguire un test di velocità con un file audio di ~1 minuto
2. Vedere i tempi reali sul tuo hardware
3. Ottenere stime automatiche per file da 10, 60 minuti
4. Confrontare `faster-whisper` (only-CPU) vs `openai-whisper auto` (CPU/CUDA)
5. Consultare lo storico risultati precedenti (salvato in `benchmark/results.json`)

---

## Impostazioni

Configurabili dalla UI (sezione **Impostazioni**) e salvate in `settings.json`:

| Impostazione | Default | Descrizione |
|---|---|---|
| `python_path` | (auto) | Path python.exe — lascia vuoto per auto |
| `pandoc_path` | (auto) | Path pandoc.exe — lascia vuoto per auto |
| `ollama_host` | `http://localhost:11434` | Host Ollama |
| `default_model_whisper` | `turbo` | Modello Whisper predefinito |
| `default_language` | `it` | Lingua trascrizione predefinita |
| `default_beam_size` | `3` | Beam size predefinito |
| `default_ollama_model` | `gemma4` | Modello Ollama predefinito |
| `default_chunk_size` | `4000` | Chunk size riassunto predefinito |
