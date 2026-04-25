"""
benchmark_whisper.py
Script autonomo per benchmarkare la velocità di trascrizione Whisper.
Viene chiamato da BenchmarkPanel con un file audio di ~1 minuto.

Uso interno — non chiamare direttamente.
Output su stdout: righe di progresso leggibili dalla UI.
"""

import argparse
import sys
import time
from pathlib import Path


def run_faster_whisper(audio_path: str, model_name: str, language: str, beam_size: int) -> float:
    """Esegue faster-whisper in modalità CPU e ritorna i secondi impiegati."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("ERRORE: faster-whisper non installato.", file=sys.stderr)
        sys.exit(1)

    print(f"[benchmark] Caricamento modello faster-whisper: {model_name} (CPU)…")
    t0 = time.time()
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    load_time = time.time() - t0
    print(f"[benchmark] Modello caricato in {load_time:.1f}s")

    print(f"[benchmark] Avvio trascrizione…")
    t1 = time.time()
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=beam_size,
    )
    # Consuma il generatore per completare la trascrizione
    text_parts = []
    for seg in segments:
        text_parts.append(seg.text)
        print(f"[benchmark] … {seg.text.strip()[:60]}")

    elapsed = time.time() - t1
    print(f"[benchmark] Trascrizione completata in {elapsed:.2f}s")
    return elapsed


def run_openai_whisper(audio_path: str, model_name: str, language: str) -> float:
    """Esegue openai-whisper (CUDA) e ritorna i secondi impiegati."""
    try:
        import whisper
    except ImportError:
        print("ERRORE: openai-whisper non installato.", file=sys.stderr)
        sys.exit(1)

    print(f"[benchmark] Caricamento modello openai-whisper: {model_name} (CUDA)…")
    t0 = time.time()
    model = whisper.load_model(model_name)
    load_time = time.time() - t0
    print(f"[benchmark] Modello caricato in {load_time:.1f}s")

    print(f"[benchmark] Avvio trascrizione…")
    t1 = time.time()
    result = model.transcribe(audio_path, language=language, verbose=True)
    elapsed = time.time() - t1
    print(f"[benchmark] Trascrizione completata in {elapsed:.2f}s")
    return elapsed


def main():
    parser = argparse.ArgumentParser(description="Benchmark Whisper per any2notes")
    parser.add_argument("input_file", help="File audio di ~1 minuto")
    parser.add_argument("output_file", help="File .txt dove scrivere la trascrizione di test")
    parser.add_argument("model_name", help="Nome modello (es. turbo, large-v3)")
    parser.add_argument("language", default="it", help="Lingua (it, en)")
    parser.add_argument("beam_size", type=int, default=3, help="Beam size")
    parser.add_argument(
        "device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="cpu = faster-whisper, cuda = openai-whisper",
    )
    args = parser.parse_args()

    audio_path = args.input_file
    if not Path(audio_path).exists():
        print(f"ERRORE: file non trovato: {audio_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[benchmark] File: {Path(audio_path).name}")
    print(f"[benchmark] Engine: {'faster-whisper CPU' if args.device == 'cpu' else 'openai-whisper CUDA'}")
    print(f"[benchmark] Modello: {args.model_name} | Lingua: {args.language} | Beam: {args.beam_size}")
    print("[benchmark] ---")

    total_start = time.time()

    if args.device == "cpu":
        transcription_time = run_faster_whisper(
            audio_path, args.model_name, args.language, args.beam_size
        )
    else:
        transcription_time = run_openai_whisper(
            audio_path, args.model_name, args.language
        )

    total_elapsed = time.time() - total_start

    # Scrivi output di test
    Path(args.output_file).write_text(
        f"[benchmark output — non usare come trascrizione reale]\n"
        f"Engine: {args.device} | Modello: {args.model_name}\n"
        f"Tempo trascrizione: {transcription_time:.2f}s\n"
        f"Tempo totale (incl. caricamento): {total_elapsed:.2f}s\n",
        encoding="utf-8",
    )

    print("[benchmark] ---")
    print(f"[benchmark] RISULTATO: trascrizione={transcription_time:.2f}s | totale={total_elapsed:.2f}s")
    print("[benchmark] DONE")


if __name__ == "__main__":
    main()
