import sys
import whisper
from pathlib import Path
from time import time

if __name__ == "__main__":
    try:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        model_name = sys.argv[3]
        language = sys.argv[4]
        beam_size = int(sys.argv[5])
    except IndexError:
        print(
            "Usage: python speech2text.py <input_file> <output_file> <model_name> <language> <beam_size>")
        sys.exit(1)
    output_path = Path(output_file)
    print(f"Loading model {model_name}...")
    model = whisper.load_model(model_name)
    start_time = time()
    print("Starting...")
    segments = model.transcribe(input_file, language=language, beam_size=beam_size)
    lines = []
    for segment in segments["segments"]:
        _s = segment["start"]
        _t = segment["text"]
        lines.append(f"[{_s:.2f}s] {_t}")
    end_time = time()
    print("Done.")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print("Worked for ", end_time - start_time, " seconds.")
