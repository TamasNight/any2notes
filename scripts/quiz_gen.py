"""
quiz_gen.py — Generatore di domande a scelta multipla da materiale didattico.

Varianti di contesto supportate:
  1  →  solo riassunto .md
  2  →  riassunto .md  + trascrizione .txt
  3  →  riassunto .md  + slide .pptx
  4  →  riassunto .md  + trascrizione .txt  + slide .pptx

Convenzione nomi file (stesso stem, stessa cartella):
  lezioni/
    01_intro.md
    01_intro.txt          ← trascrizione
    01_intro.pptx         ← slide originali

Uso:
  python quiz_gen.py --dir ./lezione --out ./quiz --n 22 --variant 3
  python quiz_gen.py --dir ./lezione --variant 4 --model qwen3.6:latest
"""

import re
import argparse
from pathlib import Path

import ollama
import pdfplumber

# ── Configurazione globale ────────────────────────────────────────────────────

MODEL        = "qwen3.6:latest"
N_QUESTIONS  = 22
OUTPUT_DIR   = "output_quiz"

# ── Estrazione testo PDF ──────────────────────────────────────────────────────

def extract_slide_text_pdf(pdf_path: Path) -> str:
    """
    Estrae il testo pagina per pagina da un PDF.
    Usa pdfplumber che preserva meglio l'ordine di lettura.
    Produce sezioni "### Pagina N" analoghe a "### Slide N" del pptx.
    """

    sections = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                text = "(pagina senza testo estraibile)"
            sections.append(f"### Pagina {idx}\n{text}")

    return "\n\n".join(sections)

# ── System prompt (comune a tutte le varianti) ────────────────────────────────

SYSTEM_PROMPT = """\
Sei un generatore di domande a scelta multipla per esami universitari.
Generi domande rigorose, tecnicamente precise e con distrattori credibili.
Rispondi SOLO con le domande nel formato richiesto, senza introduzioni, \
commenti, testo aggiuntivo o blocchi di ragionamento.\
"""

# ── Prompt per le 4 varianti ──────────────────────────────────────────────────
#
#  Ogni prompt ha:
#    - sezione REGOLE OBBLIGATORIE  (invariante)
#    - sezione FORMATO              (invariante)
#    - sezione MATERIALE            (personalizzata per la variante)
#
#  I placeholder sono:
#    {n}           numero di domande richieste
#    {md}          testo del riassunto .md
#    {transcript}  testo della trascrizione  (varianti 2, 4)
#    {slides}      testo estratto dal .pptx  (varianti 3, 4)

_RULES = """\
REGOLE OBBLIGATORIE:
1. Sfrutta TUTTO il materiale fornito per identificare i concetti chiave.
2. La risposta corretta è SEMPRE e UNICAMENTE l'opzione A).
3. Le opzioni B), C), D) devono essere plausibili ma errate: usa valori simili, \
concetti correlati ma distinti, o affermazioni parzialmente vere per creare \
distrattori efficaci che mettano alla prova la comprensione esatta.
4. Non inserire nella domanda hint o parole che rendano ovvia la risposta corretta.
5. Varia la tipologia: definizioni, applicazioni, confronti, eccezioni, valori \
numerici, relazioni causa-effetto.
6. Numera le domande in modo crescente partendo da 1.
7. Privilegia i concetti su cui il professore ha posto maggiore enfasi.\
"""

_FORMAT = """\
FORMATO OBBLIGATORIO (rispettalo alla lettera, senza deviazioni, senza testo prima o dopo):
1. Testo della domanda?
A) Risposta corretta
B) Distrattore plausibile
C) Distrattore plausibile
D) Distrattore plausibile
Risposta corretta: A\
"""

# Variante 1 — solo riassunto .md
PROMPT_V1 = f"""\
Genera {{n}} domande a scelta multipla basate ESCLUSIVAMENTE \
sul contenuto del seguente riassunto di lezione.

{_RULES}

{_FORMAT}

--- INIZIO MATERIALE ---

[RIASSUNTO]
{{md}}
[/RIASSUNTO]

--- FINE MATERIALE ---\
"""

# Variante 2 — riassunto .md + trascrizione
PROMPT_V2 = f"""\
Genera {{n}} domande a scelta multipla basate sul materiale della lezione \
che comprende un riassunto strutturato e la trascrizione integrale della lezione.
Usa il riassunto per individuare i concetti principali e la trascrizione per \
recuperare dettagli, esempi pratici ed enfasi del professore.

{_RULES}

{_FORMAT}

--- INIZIO MATERIALE ---

[RIASSUNTO]
{{md}}
[/RIASSUNTO]

[TRASCRIZIONE]
{{transcript}}
[/TRASCRIZIONE]

--- FINE MATERIALE ---\
"""

# Variante 3 — riassunto .md + slide PPTX
PROMPT_V3 = f"""\
Genera {{n}} domande a scelta multipla basate sul materiale della lezione \
che comprende un riassunto strutturato e il testo estratto dalle slide ufficiali.
Usa le slide come fonte primaria per terminologia formale e definizioni esatte; \
usa il riassunto per il filo logico della lezione.

{_RULES}

{_FORMAT}

--- INIZIO MATERIALE ---

[RIASSUNTO]
{{md}}
[/RIASSUNTO]

[SLIDE]
{{slides}}
[/SLIDE]

--- FINE MATERIALE ---\
"""

# Variante 4 — riassunto .md + trascrizione + slide PPTX
PROMPT_V4 = f"""\
Genera {{n}} domande a scelta multipla basate sul materiale completo della lezione: \
riassunto strutturato, testo estratto dalle slide ufficiali e trascrizione integrale.
Usa le slide per la terminologia formale e le definizioni esatte, \
la trascrizione per esempi pratici ed enfasi del professore, \
il riassunto per il filo logico e la gerarchia dei concetti.

{_RULES}

{_FORMAT}

--- INIZIO MATERIALE ---

[RIASSUNTO]
{{md}}
[/RIASSUNTO]

[SLIDE]
{{slides}}
[/SLIDE]

[TRASCRIZIONE]
{{transcript}}
[/TRASCRIZIONE]

--- FINE MATERIALE ---\
"""

PROMPTS = {1: PROMPT_V1, 2: PROMPT_V2, 3: PROMPT_V3, 4: PROMPT_V4}

VARIANT_LABEL = {
    1: "md",
    2: "md + trascrizione",
    3: "md + slide",
    4: "md + slide + trascrizione",
}

# ── Assemblaggio contesto ─────────────────────────────────────────────────────

def extract_transcription(base: Path) -> list:
    txt_files = list(sorted(base.glob("*.txt")))
    if len(txt_files) == 0:
        print(f"  ✗ Trascrizioni non trovate in: {str(base)}")
    transcript = []
    for tr_path in txt_files:
        transcript.append(tr_path.read_text(encoding="utf-8"))
    return transcript

def build_user_message(md_path: Path, variant: int, n: int) -> str | None:
    """
    Legge i file necessari per la variante scelta e formatta il prompt.
    Ritorna None se manca un file obbligatorio per quella variante.
    """
    stem = md_path.stem
    base = md_path.parent

    md_text = md_path.read_text(encoding="utf-8")

    if variant == 1:
        return PROMPTS[1].format(n=n, md=md_text)

    if variant == 2:
        transcript = extract_transcription(base)
        if len(transcript) == 0:
            return None
        return PROMPTS[2].format(n=n, md=md_text, transcript="".join(transcript))

    if variant == 3:
        pdf_path = base.glob("*.pdf").__next__().with_suffix(".pdf")
        if not pdf_path.exists():
            print(f"  ✗ PDF non trovato: {pdf_path}")
            return None
        slides = extract_slide_text_pdf(pdf_path)
        return PROMPTS[3].format(n=n, md=md_text, slides=slides)

    if variant == 4:
        pdf_path =base.glob("*.pdf").__next__().with_suffix(".pdf")
        print(f"  PDF trovato: {pdf_path}")
        transcript = extract_transcription(base)
        if len(transcript) == 0:
            return None
        if not pdf_path.exists():
            print(f"  ✗ PDF non trovato: {pdf_path}")
            return None
        slides     = extract_slide_text_pdf(pdf_path)
        return PROMPTS[4].format(n=n, md=md_text, transcript="".join(transcript), slides=slides)

    raise ValueError(f"Variante non valida: {variant}. Scegli tra 1, 2, 3, 4.")

# ── Validazione output ────────────────────────────────────────────────────────

QUESTION_RE = re.compile(
    r"^\d+\.\s.+\n"
    r"A\)\s.+\n"
    r"B\)\s.+\n"
    r"C\)\s.+\n"
    r"D\)\s.+\n"
    r"Risposta corretta:\s*A",
    re.MULTILINE,
)

def validate_output(text: str) -> tuple[bool, int]:
    matches = QUESTION_RE.findall(text)
    return len(matches) > 0, len(matches)

# ── Generazione ───────────────────────────────────────────────────────────────

def generate_questions(user_msg: str) -> str:
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        options={
            "temperature": 0.7,
        },
    )
    return response["message"]["content"]

# ── Pipeline per singolo file ─────────────────────────────────────────────────

def process_file(md_path: Path, variant: int, n: int, retry: int, dry: bool=False) -> bool:
    out_path = OUTPUT_DIR / Path(f"{md_path.parent}_{md_path.with_suffix(".quiz.md").name}")

    user_msg = build_user_message(md_path, variant, n)
    if user_msg is None:
        return False

    estimated_tokens = len(user_msg) // 4
    print(f"  Contesto stimato: ~{estimated_tokens:,} token di input")

    if dry:
        print(f"saving quiz to {out_path}...")
        return False

    raw = ""
    for attempt in range(1, retry + 1):
        print(f"  [{attempt}/{retry}] Generazione in corso...")
        try:
            raw = generate_questions(user_msg)

            ok, n_found = validate_output(raw)
            if ok:
                out_path.mkdir(parents=True, exist_ok=True)
                out_path.write_text(raw, encoding="utf-8")
                print(f"  ✓ {n_found} domande salvate → {out_path.name}")
                return True
        except Exception as e:
            print(f"  ✗ Errore (tentativo {attempt}/{retry})\n{e}")

    # Salva comunque per ispezione manuale
    out_path.write_text(raw, encoding="utf-8")
    print(f"  ⚠ Output grezzo salvato per revisione → {out_path.name}")
    return False

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    global OUTPUT_DIR, MODEL
    parser = argparse.ArgumentParser(
        description="Genera quiz a scelta multipla da materiale didattico con Ollama.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-d","--dir", type=str, default="lezioni",
        help="Cartella contenente i file .md.",
    )
    parser.add_argument(
        "-o", "--out", type=str, default=OUTPUT_DIR,
        help="Cartella di output per il file .quiz.md.",
    )
    parser.add_argument(
        "-n","--number", type=int, default=N_QUESTIONS,
        help="Numero di domande da generare per ogni file.",
    )
    parser.add_argument(
        "-v", "--variant", type=int, choices=[1, 2, 3, 4], default=1,
        help=(
            "Variante di contesto:\n"
            "  1 → solo .md\n"
            "  2 → .md + trascrizione .txt\n"
            "  3 → .md + slide .pdf\n"
            "  4 → .md + slide .pdf + trascrizione .txt"
        ),
    )
    parser.add_argument("-m", "--model", type=str, default=MODEL, help="Modello Ollama da usare.")
    parser.add_argument("-r", "--retry", type=int, default=1,    help="Tentativi per file in caso di formato errato.")
    parser.add_argument("--dry-run", action="store_true", help="Just display the md files to be processed, without generating the quiz.")
    args = parser.parse_args()

    OUTPUT_DIR = Path(args.out)
    INPUT_DIR  = Path(args.dir)
    MODEL      = args.model
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    md_files = sorted(INPUT_DIR.rglob("*.md"))
    if not md_files:
        print(f"Nessun file .md trovato in '{args.dir}'.")
        return

    print(
        f"File trovati : {len(md_files)}\n"
        f"Modello      : {MODEL}\n"
        f"Variante     : {args.variant} ({VARIANT_LABEL[args.variant]})\n"
        f"Domande/file : {args.number}\n"
    )

    for md in md_files:
        print(f"→ {md.name}")
        process_file(md, args.variant, args.number, args.retry, args.dry_run)
        print()

    print("Processo completato con successo.")



if __name__ == "__main__":
    main()