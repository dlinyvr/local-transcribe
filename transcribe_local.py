#!/usr/bin/env python3
"""Transcribe a local video/audio file with faster-whisper.

If the file is longer than 20 min, it is first split (lossless ffmpeg stream copy)
into 20-min parts saved NEXT TO the source file, then each part is transcribed.

Usage (run with the skill's own Python, .venv/bin/python):
  python3 transcribe_local.py <file> [--model medium] [--chunk-min 20] [--no-split]
Outputs: <stem>.transcript.txt next to the source (one block per part, with headers),
rewritten after every part so a crash never loses finished work.

"""
import argparse, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import settings

S = settings()

def duration(p):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", str(p)], text=True)
    return float(out.strip())

def split(src, chunk_s):
    pat = src.with_name(f"{src.stem}-part%02d{src.suffix}")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
                    "-c", "copy", "-map", "0", "-f", "segment", "-segment_time", str(chunk_s),
                    "-reset_timestamps", "1", str(pat)], check=True)
    return sorted(src.parent.glob(f"{src.stem}-part*{src.suffix}"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--model", default=S["WHISPER_MODEL"])
    ap.add_argument("--chunk-min", type=float, default=20); ap.add_argument("--no-split", action="store_true")
    ap.add_argument("--language", default=S["LANGUAGE"], help="force a language (auto-detect can guess wrong on short clips); empty = auto")
    a = ap.parse_args()
    src = Path(a.file).expanduser().resolve()
    dur = duration(src)
    print(f"[info] {src.name}: {dur/60:.1f} min", file=sys.stderr)
    parts = [src]
    if dur > a.chunk_min * 60 and not a.no_split:
        parts = split(src, int(a.chunk_min * 60))
        print(f"[info] split into {len(parts)} parts", file=sys.stderr)
    from faster_whisper import WhisperModel
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    out = src.with_name(f"{src.stem}.transcript.txt")
    blocks = []
    for i, p in enumerate(parts, 1):
        print(f"[info] transcribing {p.name} ({i}/{len(parts)})", file=sys.stderr, flush=True)
        segs, _ = model.transcribe(str(p), beam_size=5, language=(a.language or None))
        text = " ".join(s.text.strip() for s in segs)
        blocks.append(f"## Part {i} — {p.name}\n\n{text}\n" if len(parts) > 1 else text + "\n")
        out.write_text("\n".join(blocks))
    print(f"[done] {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
