#!/usr/bin/env python3
"""Transcribe YouTube videos, Shorts, channels or playlists into dated markdown files.

Run with the skill's own Python:  ~/.claude/skills/transcribe/.venv/bin/python transcribe.py <url> [<url> ...]

Per run:
  1. duplicate check  -> the ledger skips anything already done (repeat channel runs fetch only new uploads)
  2. captions         -> free: youtube-transcript-api, then yt-dlp caption files
                         paid, optional: Apify (--method apify, only after the user says yes; --cap is a hard USD stop)
  3. Whisper          -> videos with no captions are downloaded and transcribed on this computer (transcribe_local.py)
  4. save             -> <TRANSCRIPTS_DIR>/<channel>/YYYY-MM-DD-<id>-<title>.md
  5. record           -> ledger.py record (method, path, words, cost, publish date)

Options:
  --method free|apify   --cap 1.0 (USD)   --no-whisper   --whisper-max 10   --limit N   --timestamps
  --out-root DIR        --no-record      (test runs)
Safety stops (each means: stop and ask the user):
  5 caption misses in a row = YouTube is rate-limiting (429). Offer to wait, or Apify with a cost estimate.
  more than --whisper-max videos need Whisper = hours of computer time. Ask first.
"""
import argparse, ast, concurrent.futures as cf, datetime as dt, json, subprocess, sys, tempfile, threading, time, urllib.request
from pathlib import Path

from common import (SKILL_DIR, is_channel, method_1_transcript_api, method_2_yt_dlp_subs, settings, slugify,
                    video_id, ytmeta)

S = settings()
LEDGER = SKILL_DIR / "ledger.py"
TLOCAL = SKILL_DIR / "transcribe_local.py"
TODAY = dt.date.today().isoformat()
lock = threading.Lock()


def new_ids(targets):
    out = subprocess.run([sys.executable, str(LEDGER), "check", *targets], capture_output=True, text=True).stdout
    for l in out.splitlines():
        if l.startswith(("CHANNEL", "DONE", "BAD")):
            print(l, flush=True)
    return [l.split()[1] for l in out.splitlines() if l.strip().startswith("NEW")]


def get(url, data=None, timeout=60):
    r = urllib.request.Request(url, data=data, headers={"content-type": "application/json", "User-Agent": "local-transcribe"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def apify_usage(token):
    return get(f"https://api.apify.com/v2/users/me/limits?token={token}")["data"]["current"]["monthlyUsageUsd"]


def fetch_apify(vid, token):
    d = get(f"https://api.apify.com/v2/acts/starvibe~youtube-video-transcript/run-sync-get-dataset-items?token={token}",
            json.dumps({"youtube_url": f"https://www.youtube.com/watch?v={vid}", "language": S["LANGUAGE"]}).encode(), timeout=600)
    x = d[0] if d else {}
    t = x.get("transcript")
    if isinstance(t, str):
        try:
            t = ast.literal_eval(t)
        except Exception:
            pass
    text = t.strip() if isinstance(t, str) else " ".join(s["text"].strip() for s in (t or []))
    meta = {"title": x.get("title"), "published": (x.get("published_at") or "")[:10], "views": x.get("view_count"),
            "likes": x.get("like_count"), "duration": x.get("duration_seconds"), "subs": x.get("subscriber_count"),
            "description": x.get("description") or "", "channel": x.get("channel_name") or "", "handle": ""}
    return text, meta, "apify:starvibe/youtube-video-transcript", x.get("message")


def fetch_free(vid, timestamps=False):
    text = method_1_transcript_api(vid, timestamps, S["LANGUAGE"])
    if text:
        return text, "youtube-transcript-api"
    if timestamps:
        return None, ""
    with tempfile.TemporaryDirectory() as t:
        return method_2_yt_dlp_subs(vid, Path(t), S["LANGUAGE"]), "yt-dlp subs"


def fetch_whisper(vid):
    with tempfile.TemporaryDirectory() as t:
        subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "-f", "ba", "-x", "--audio-format", "m4a",
                        "-o", f"{t}/{vid}.%(ext)s", f"https://www.youtube.com/watch?v={vid}"], check=True)
        audio = next(Path(t).glob(f"{vid}.*"))
        subprocess.run([sys.executable, str(TLOCAL), str(audio)], check=True)
        txt = audio.with_name(f"{audio.stem}.transcript.txt")
        return txt.read_text().strip() if txt.exists() else ""


def save(root, vid, text, m, method, record, cost, suffix=""):
    channel = m.get("channel") or "misc"
    out = Path(root) / (slugify(channel) or "misc")
    out.mkdir(parents=True, exist_ok=True)
    pub = m.get("published") or ""
    f = out / f"{pub}-{vid}-{slugify(m.get('title') or vid)}{suffix}.md"
    f.write_text(f"# {m.get('title')}\n\nhttps://www.youtube.com/watch?v={vid}\n"
                 f"published {pub} | views {m.get('views')} | likes {m.get('likes')} | duration {m.get('duration')}s | "
                 f"subs {m.get('subs')} | channel {channel} ({m.get('handle')})\n"
                 f"method {method} | fetched {TODAY}\n\n## Description\n\n{m.get('description')}\n\n## Transcript\n\n{text}\n",
                 encoding="utf-8")
    words = len(text.split())
    if record:
        tag = "apify" if method.startswith("apify") else ("whisper" if method.startswith("whisper") else
                                                          "api" if "transcript-api" in method else "yt-dlp")
        subprocess.run([sys.executable, str(LEDGER), "record", f"--id={vid}", "--status", "done", "--method", tag,
                        "--path", str(f), "--words", str(words), "--cost", str(cost), "--published", pub,
                        "--channel", channel, "--title", m.get("title") or vid], capture_output=True)
    with lock:
        mf = out / "_meta.json"
        meta = json.loads(mf.read_text()) if mf.exists() else {}
        meta[vid] = {"title": m.get("title"), "published": pub, "views": m.get("views"), "duration": m.get("duration"),
                     "file": str(f), "words": words, "method": method}
        mf.write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"saved {f}", flush=True)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+", help="video URLs or ids, channel or playlist URLs")
    ap.add_argument("--method", choices=["free", "apify"], default="free")
    ap.add_argument("--cap", type=float, default=1.0, help="Apify USD cap for this run")
    ap.add_argument("--no-whisper", action="store_true")
    ap.add_argument("--whisper-max", type=int, default=10)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--timestamps", action="store_true", help="[MM:SS] lines (free captions only)")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--out-root", default=S["TRANSCRIPTS_DIR"])
    ap.add_argument("--no-record", action="store_true")
    a = ap.parse_args()

    if a.timestamps:  # timestamped copy: always fetch, saved as a separate file, not counted in the ledger
        ids = [i for i in (video_id(t) for t in a.targets) if i]
        record = False
    else:
        ids = new_ids(a.targets)
        record = not a.no_record
    if a.limit:
        ids = ids[:a.limit]
    print(f"{len(ids)} to fetch -> {a.out_root} (method {a.method}, whisper {'off' if a.no_whisper else 'on'})", flush=True)
    if not ids:
        return
    no_caps, ok = [], 0

    if a.method == "apify":
        token = S["APIFY_TOKEN"]
        if not token:
            sys.exit("APIFY_TOKEN is empty in .env. Run onboarding or use --method free.")
        start = apify_usage(token)
        stop = threading.Event()
        print(f"Apify usage this month ${start:.2f}; hard stop at ${start + a.cap:.2f}", flush=True)

        def work(vid):
            if stop.is_set():
                return
            text, m, how, msg = fetch_apify(vid, token)
            if not text:
                no_caps.append(vid)
                print("no captions", vid, msg or "", flush=True)
                return
            save(a.out_root, vid, text, m, how, record, 0.005)
            if apify_usage(token) - start >= a.cap:
                stop.set()
                print("CAP REACHED, stopping", flush=True)
            return 1

        with cf.ThreadPoolExecutor(a.threads) as ex:
            ok = sum(1 for r in ex.map(work, ids) if r)
    else:
        streak = 0
        for n, vid in enumerate(ids):
            text, how = fetch_free(vid, a.timestamps)
            if not text:
                no_caps.append(vid)
                streak += 1
                print("no captions", vid, flush=True)
                if streak >= 5:
                    left = len(ids) - n - 1 + 5
                    no_caps = no_caps[:-5]
                    print(f"STOP: 5 misses in a row, probably YouTube rate-limiting (429). {left} videos left. "
                          f"Ask the user: wait and retry later (free), or use Apify (about {left * 0.005:.2f} USD).", flush=True)
                    break
                time.sleep(a.delay)
                continue
            streak = 0
            save(a.out_root, vid, text, ytmeta(vid), how, record, 0, "-timestamps" if a.timestamps else "")
            ok += 1
            time.sleep(a.delay)

    if no_caps and a.timestamps:
        print(f"No captions, so no timestamps for: {' '.join(no_caps)}", flush=True)
    elif no_caps and not a.no_whisper:
        if len(no_caps) > a.whisper_max:
            print(f"WHISPER SKIPPED: {len(no_caps)} videos need it (more than --whisper-max {a.whisper_max}). "
                  f"Ask the user, then rerun with these ids and a higher --whisper-max: {' '.join(no_caps)}", flush=True)
        else:
            print(f"Whisper for {len(no_caps)} video(s) with no captions: {' '.join(no_caps)}", flush=True)
            for vid in no_caps:
                try:
                    text = fetch_whisper(vid)
                except Exception as e:
                    print("WHISPER ERROR", vid, str(e)[:160], flush=True)
                    continue
                if text:
                    save(a.out_root, vid, text, ytmeta(vid), f"whisper {S['WHISPER_MODEL']} (no captions)", record, 0)
                    ok += 1
    elif no_caps:
        print(f"No captions and Whisper is off: {' '.join(no_caps)}", flush=True)
    print(f"done: {ok} saved under {a.out_root}", flush=True)


if __name__ == "__main__":
    main()
