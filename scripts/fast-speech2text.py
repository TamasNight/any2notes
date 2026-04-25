from faster_whisper import WhisperModel
from pathlib import Path
import sys
from time import time

if __name__ == "__main__":
    try:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        model_name = sys.argv[3]
        language = sys.argv[4]
        beam_size = int(sys.argv[5])
        device = sys.argv[6]
    except IndexError:
        print("Usage: python fast-speech2text.py <input_file> <output_file> <model_name> <language> <beam_size> <device>")
        sys.exit(1)
    output_path = Path(output_file)
    print(f"Loading model {model_name}...")
    if device == "cpu":
        model = WhisperModel(model_name, device="cpu")
    else:
        model = WhisperModel(model_name, device="cuda", compute_type="float16")
    start_time = time()
    print("Starting...")
    segments, info = model.transcribe(input_file, beam_size=beam_size, language=language)
    lines = []
    for segment in segments:
        lines.append(f"[{segment.start:.2f}s] {segment.text}")
    end_time = time()
    print("Done.")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print("Worked for ", end_time - start_time, " seconds.")