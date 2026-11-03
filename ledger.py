#!/usr/bin/env python3
"""Transcribe ledger: never transcribe (or pay for) the same video or channel twice.

Ledger: ledger.jsonl  (next to this script; one JSON object per video; last row per id wins)
        channels.jsonl (one row per channel listing snapshot)

  ledger.py check <url|id|@handle-url>… # prints DONE / NEW per video; channel URLs are listed (yt-dlp, free) and diffed
  ledger.py record --id ID --status done|failed|partial --method M [--title T --channel C --path P --words N --cost USD --channel-url U]
  ledger.py dates                       # backfill/repair `published` from saved file headers; lists rows missing a date
  ledger.py stats

`check` exits 0 always; read its NEW list. `record` refuses to overwrite a `done` row unless --force.
"""
import argparse, json, os, re, subprocess, sys, datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "ledger.jsonl"
CHANNELS = HERE / "channels.jsonl"
ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|/live/)([A-Za-z0-9_-]{11})")
BARE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def today():
    return dt.date.today().isoformat()


def load():
    rows = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                rows[r["id"]] = r
    return rows


def append(path, row):
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def vid_of(s):
    s = s.strip()
    if BARE.match(s):
        return s
    m = ID_RE.search(s)
    return m.group(1) if m else None


def is_channel(s):
    return bool(re.search(r"youtube\.com/(@|channel/|c/|user/|playlist\?)", s))


def list_channel(url):
    base = url.split("?")[0].rstrip("/")
    if "playlist" not in url and not re.search(r"/(videos|shorts|streams)$", base):
        targets = [base + "/videos", base + "/shorts", base + "/streams"]
    else:
        targets = [url]
    out = {}
    for t in targets:
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "--print", "%(id)s|%(duration)s|%(title)s", t],
                           capture_output=True, text=True)
        for line in r.stdout.splitlines():
            p = line.split("|", 2)
            if len(p) == 3 and BARE.match(p[0]):
                out[p[0]] = {"id": p[0], "duration": p[1], "title": p[2], "tab": t.rsplit("/", 1)[-1]}
    return list(out.values())


def cmd_check(a):
    rows = load()
    for item in a.items:
        if is_channel(item):
            vids = list_channel(item)
            new = [v for v in vids if rows.get(v["id"], {}).get("status") != "done"]
            done = len(vids) - len(new)
            append(CHANNELS, {"channel_url": item, "checked": today(), "listed": len(vids), "done": done,
                              "new_ids": [v["id"] for v in new]})
            tot = sum(int(v["duration"] or 0) for v in new if str(v["duration"]).isdigit())
            print(f"CHANNEL {item}: listed {len(vids)}, already done {done}, NEW {len(new)} (~{tot/3600:.1f} h)")
            for v in new:
                print(f"  NEW  {v['id']}  {v['duration']:>5}s  [{v['tab']}] {v['title']}")
        else:
            i = vid_of(item)
            if not i:
                print(f"BAD  {item}")
                continue
            r = rows.get(i)
            if r and r.get("status") == "done":
                print(f"DONE {i}  {r.get('recorded')}  via {r.get('method')}  {r.get('path','(no file)')}")
            else:
                print(f"NEW  {i}" + (f"  (prior status: {r['status']})" if r else ""))


def cmd_record(a):
    rows = load()
    old = rows.get(a.id)
    if old and old.get("status") == "done" and not a.force:
        sys.exit(f"REFUSED: {a.id} already done ({old.get('path')}). Use --force to re-record.")
    r = {"id": a.id, "url": f"https://youtu.be/{a.id}", "status": a.status, "method": a.method, "recorded": today()}
    for k in ("title", "channel", "path", "words", "cost", "channel_url", "published"):
        v = getattr(a, k)
        if v is not None:
            r[k] = v
    append(LEDGER, r)
    print("recorded", json.dumps(r, ensure_ascii=False))


def cmd_dates(a):
    rows = load(); fixed = missing = 0
    for i, r in rows.items():
        if r.get("published") or r.get("status") != "done":
            continue
        d = None
        p = Path(r.get("path", ""))
        if p.is_file():
            m = re.search(r"(?:published|Uploaded:?|upload date:?)\s*(\d{4}-\d{2}-\d{2})", p.read_text(errors="ignore")[:1500], re.I)
            d = m.group(1) if m else None
        if d:
            append(LEDGER, {**r, "published": d, "recorded": r.get("recorded")}); fixed += 1
        else:
            missing += 1; print("NO DATE", i, r.get("title", "")[:60])
    print(f"dates: fixed {fixed}, still missing {missing}")


def cmd_stats(a):
    rows = load()
    from collections import Counter
    print(Counter(r.get("status") for r in rows.values()), "total", len(rows))
    print("spend USD:", round(sum(float(r.get("cost") or 0) for r in rows.values()), 4))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("check"); c.add_argument("items", nargs="+"); c.set_defaults(f=cmd_check)
    r = sp.add_parser("record"); r.add_argument("--id", required=True)
    r.add_argument("--status", required=True, choices=["done", "failed", "partial"])
    r.add_argument("--method", required=True)
    r.add_argument("--title"); r.add_argument("--channel"); r.add_argument("--path")
    r.add_argument("--words", type=int); r.add_argument("--cost", type=float); r.add_argument("--channel-url"); r.add_argument("--published", help="YYYY-MM-DD upload date (required for SEO recency)")
    r.add_argument("--force", action="store_true"); r.set_defaults(f=cmd_record)
    sp.add_parser("dates").set_defaults(f=cmd_dates)
    sp.add_parser("stats").set_defaults(f=cmd_stats)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
