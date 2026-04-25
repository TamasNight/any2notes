import argparse
from tqdm import tqdm
import sys
import ollama
from pathlib import Path


PROMPT_TEMPLATE = """Sei un assistente specializzato in scienze naturali.
Di seguito trovi la trascrizione (o una parte) di una lezione universitaria in italiano.
Produci un riassunto strutturato in italiano con:
- Argomenti principali trattati
- Concetti chiave e definizioni
- Eventuali esempi o organismi citati

Trascrizione:
{chunk}

Riassunto:"""

MERGE_PROMPT = """Sei un assistente specializzato in scienze naturali.
Hai riassunto le trascrizioni di una lezione universitaria in italiano, generando dei riassunti parziali.
Unifica questi riassunti parziali in un unico documento coerente, dettagliato e ben strutturato in italiano:

{summaries}"""

def chunk_text(text: str, max_chars: int) -> list[str]:
    # Divide per frasi, non a metà parola
    sentences = text.replace(". ", ".|").split("|")
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) > max_chars:
            chunks.append(current.strip())
            current = s
        else:
            current += " " + s
    if current:
        chunks.append(current.strip())
    return chunks

def summarize(text: str, model, max_chunk, save_parts, part_path) -> str:
    chunks = chunk_text(text, max_chunk)
    summaries = []
    for i, chunk in tqdm(enumerate(chunks), total=len(chunks), desc="Riassunto chunk"):
        # print(f"  Riassunto chunk {i+1}/{len(chunks)}...")
        response = ollama.chat(model=model, messages=[
            {"role": "user", "content": PROMPT_TEMPLATE.format(chunk=chunk)}
        ])
        summaries.append(response["message"]["content"])

    # Se c'è un solo chunk, già finito
    if len(summaries) == 1:
        return summaries[0]

    if save_parts:
        path = Path(part_path)
        parts_path = Path(path.stem)
        parts_path.mkdir(parents=True, exist_ok=True)
        for i, summary in enumerate(summaries):
            (parts_path / f"part_{i}.md").write_text(summary)
        print(f"Salvataggio riassunti in {parts_path}")

    print("Unificazione chunk")
    # Altrimenti riassumi i riassunti
    combined = "\n\n---\n\n".join(summaries)
    response = ollama.chat(model=model, messages=[
        {"role": "user", "content": MERGE_PROMPT.format(summaries=combined)}
    ])
    return response["message"]["content"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='Text2Notes',
        description='Create a summary of a list of text files')
    parser.add_argument('-i', '--input', required=True, nargs='+', help='Path to the input file(s')
    parser.add_argument('-o', '--output', default="summary.md")
    parser.add_argument('-p', '--parts', action="store_true",)
    parser.add_argument('-m', '--model', default="gemma4",
                        help="Ollama model to use, installed models: 'gemma4', 'qwen3.6'; online models: 'minimax-m2.7:cloud'")
    parser.add_argument('-c', '--chunk-size', default=6000, type=int,
                        help="Maximum number of characters per chunk")
    args = parser.parse_args()

    text_to_summarize = []
    for input_path in args.input:
        input_file = Path(input_path)
        if not input_file.exists():
            print(f"Errore: file non trovato: {input_path}")
            sys.exit(1)
        text_to_summarize.append(input_file.read_text())

    texts = "\n".join(text_to_summarize)
    print(f"Loaded text to summarize.")
    summarized_text = summarize(texts, args.model, args.chunk_size, args.parts, args.output)
    print(f"Summary generated. Writing to {args.ouput}...")
    output_path = Path(args.ouput)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summarized_text, encoding="utf-8")
    print("Done.")
