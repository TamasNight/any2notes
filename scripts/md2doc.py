import argparse
import pypandoc
from pathlib import Path

def convert_md(input_files, output_format, output_file):
    # Mapping per le estensioni corrette
    output_path = Path(output_file)

    for file_path in input_files:
        path = Path(file_path)

        # Controllo se il file esiste e se è un .md
        if not path.exists():
            print(f"Errore: Il file {file_path} non esiste.")
            continue

        if path.suffix.lower() != '.md':
            print(f"Salto {file_path}: Non è un file Markdown.")
            continue

        try:
            print(f"Conversione in corso: {path.name} -> {output_path.name}...")

            # Conversione effettiva
            pypandoc.convert_file(str(path), output_format, outputfile=str(output_path))

            print(f"Successo! File salvato in: {output_file}")
        except Exception as e:
            print(f"Errore durante la conversione di {file_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Converti file Markdown in Word (.docx) o PDF.")

    # Argomento posizionale: uno o più file
    parser.add_argument('files', nargs='+', help="Percorso del file o dei file .md da convertire")

    # Argomento opzionale per il formato (default: docx)
    parser.add_argument('-f', '--format', choices=['docx', 'pdf'], default='docx',
                        help="Formato di output: 'docx' (default) o 'pdf'")
    parser.add_argument('-o', '--output', help="File di output")
    args = parser.parse_args()

    convert_md(args.files, args.format, args.output)

if __name__ == "__main__":
    main()