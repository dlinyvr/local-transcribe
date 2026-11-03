"""Shared helpers: settings, YouTube metadata, the two free caption methods."""
import json, os, re, subprocess, sys
from pathlib import Path
from typing import Optional

SKILL_DIR = Path(__file__).resolve().parent
DEFAULTS = {
    "TRANSCRIPTS_DIR": "~/transcripts/youtube",
    "WHISPER_MODEL": "medium",
    "LANGUAGE": "en",
    "APIFY_TOKEN": "",
}


def settings() -> dict:
    s = dict(DEFAULTS)
    env = SKILL_DIR / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*)", line)
            if m and not line.lstrip().startswith("#"):
                s[m.group(1)] = m.group(2).strip().strip("'\"")
    for k in DEFAULTS:  # real environment variables win
        if os.environ.get(k):
            s[k] = os.environ[k]
    for k in ("TRANSCRIPTS_DIR",):
        s[k] = str(Path(os.path.expanduser(s[k])))
    return s


def slugify(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")[:60]


ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|/live/)([A-Za-z0-9_-]{11})")
BARE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def video_id(s: str) -> Optional[str]:
    s = s.strip()
    if BARE.match(s):
        return s
    m = ID_RE.search(s)
    return m.group(1) if m else None


def is_channel(s: str) -> bool:
    return bool(re.search(r"youtube\.com/(@|channel/|c/|user/|playlist\?)", s))


def ytmeta(vid: str) -> dict:
    """Title, publish date, stats and channel for one video (yt-dlp, free)."""
    try:
        out = subprocess.run([sys.executable, "-m", "yt_dlp", "-J", "--skip-download", "--no-warnings",
                              f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, timeout=120).stdout
        j = json.loads(out)
    except Exception:
        return {}
    d = j.get("upload_date") or ""
    return {"title": j.get("title"), "published": f"{d[:4]}-{d[4:6]}-{d[6:]}" if d else "",
            "views": j.get("view_count"), "likes": j.get("like_count"), "duration": j.get("duration"),
            "subs": j.get("channel_follower_count"), "description": j.get("description") or "",
            "channel": j.get("channel") or j.get("uploader") or "", "handle": j.get("uploader_id") or ""}


def clean_text(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def method_1_transcript_api(vid: str, timestamps: bool = False, lang: str = "en") -> Optional[str]:
    """YouTube's captions through youtube-transcript-api. Free, fast, no download."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        langs = [lang, "en", "en-US", "en-GB"]
        if hasattr(YouTubeTranscriptApi, "get_transcript"):  # library < 1.0
            items = [(e["start"], e["text"]) for e in YouTubeTranscriptApi.get_transcript(vid, languages=langs)]
        else:
            items = [(s.start, s.text) for s in YouTubeTranscriptApi().fetch(vid, languages=langs)]
        if timestamps:
            return "\n".join(f"[{int(t // 60):02d}:{int(t % 60):02d}] {x.strip()}" for t, x in items)
        return clean_text(" ".join(x for _, x in items))
    except Exception:
        return None


def parse_vtt(vtt: str) -> str:
    parsed, prev, out = [], None, []
    for line in vtt.split("\n"):
        line = line.strip()
        if (not line or line.startswith(("WEBVTT", "NOTE", "STYLE")) or "-->" in line
                or re.match(r"^\d+$", line) or re.match(r"^\d{2}:\d{2}", line)):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            parsed.append(line)
    for line in parsed:
        if line != prev:
            out.append(line)
            prev = line
    return " ".join(out)


def method_2_yt_dlp_subs(vid: str, work_dir: Path, lang: str = "en") -> Optional[str]:
    """Caption file through yt-dlp. Catches videos method 1 misses."""
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "writesubtitles": True, "writeautomaticsub": True,
                "subtitleslangs": [lang], "subtitlesformat": "vtt", "skip_download": True,
                "outtmpl": str(work_dir / vid)}
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={vid}"])
        for f in work_dir.glob(f"{vid}*.vtt"):
            text = parse_vtt(f.read_text(encoding="utf-8"))
            return clean_text(text) if text else None
    except Exception:
        pass
    return None
