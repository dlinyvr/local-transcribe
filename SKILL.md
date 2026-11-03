---
name: transcribe
description: Transcribe YouTube videos, Shorts, whole channels or playlists, and video or audio files on this computer, into tidy dated markdown files. Free by default (YouTube captions first, then speech-to-text on this computer with faster-whisper). Never transcribes the same video twice. Optional paid fallback (Apify) only with the user's yes. Use when the user says "/transcribe", "transcribe this", pastes a YouTube link to transcribe, or gives a path to a video or audio file to turn into text.
---

# /transcribe

Turns videos into text you can search, quote and feed to Claude. Everything runs from this skill's folder
(call it SKILL_DIR: the folder that holds this SKILL.md, normally `~/.claude/skills/transcribe`).
Run every script with the skill's own Python: `SKILL_DIR/.venv/bin/python`.

## First run: onboarding (always check this before any job)

If `SKILL_DIR/.onboarded` does not exist, or a needed tool or setting is missing, do this first. Assume the user
has never used a Claude Code skill and has not read the README. Be patient and plain.

**The install rule: never install anything without asking, even once.** For every install: say what it is and
why this skill needs it (one or two sentences), say how big or slow it is if that matters, list the options if
there are any with a one-line trade-off each, recommend a default, show the exact command, and ask "OK to run
it?". Run it only after a yes and confirm it worked. If they say no, explain what will not work without it.

1. **Hello.** One line: "I'll set up /transcribe. It takes a few minutes and I'll ask before installing anything."
2. **Python.** Check `python3 --version` (3.9 or newer). If missing: macOS `brew install python` (if Homebrew is
   missing, explain it and offer the official installer from https://brew.sh), Windows `winget install
   Python.Python.3.12`, Linux `sudo apt install python3 python3-venv`.
3. **The skill's own Python folder + core packages** (ask first). Explain: "I'll make a private Python folder
   inside the skill (`.venv`) so nothing touches the rest of your computer, and install two small free tools:
   youtube-transcript-api (reads YouTube's captions) and yt-dlp (lists channels, gets publish dates)."
   `python3 -m venv SKILL_DIR/.venv && SKILL_DIR/.venv/bin/pip install -q -r SKILL_DIR/requirements.txt`
4. **Where to save transcripts** (always ask, never pick silently). Suggest `~/transcripts/youtube` as the
   default and accept any folder they name. Explain they get one sub-folder per YouTube channel. Copy
   `.env.example` to `.env` if needed and write their answer as `TRANSCRIPTS_DIR`.
5. **Speech-to-text for videos with no captions and for local files** (optional, ask). Explain: "Most YouTube
   videos have captions and need nothing more. For videos without captions, and for files on your computer,
   I can turn the audio into text right here on your computer for free with faster-whisper. It needs two
   installs: faster-whisper and ffmpeg." If they want it:
   - **faster-whisper** (recommended: faster than the original OpenAI Whisper, same accuracy, runs fine on a
     normal laptop CPU): `SKILL_DIR/.venv/bin/pip install -q -r SKILL_DIR/requirements-whisper.txt`
   - **Pick a model size** (downloads once on first use; bigger = more accurate but slower):

     | Model | Download | Speed on a laptop CPU | When to pick it |
     |---|---|---|---|
     | tiny | about 75 MB | very fast | quick rough drafts |
     | base | about 145 MB | fast | rough drafts, clear audio |
     | small | about 480 MB | moderate | older or slower computers |
     | **medium (recommended)** | about 1.5 GB | about 40 minutes per 110 minutes of audio | the best balance for most people |
     | large-v3-turbo | about 1.6 GB | similar to medium | newer, fast computers |
     | large-v3 | about 3 GB | slow | the best accuracy, if you can wait |

     Write the choice as `WHISPER_MODEL` in `.env`. Also ask the main language of their videos (`LANGUAGE`,
     default `en`; empty lets Whisper guess, which can misfire on short clips).
   - **ffmpeg** (free; measures, splits and extracts audio): macOS `brew install ffmpeg`, Windows
     `winget install Gyan.FFmpeg`, Linux `sudo apt install ffmpeg`.
6. **Apify (optional, paid).** Explain: "Sometimes YouTube temporarily blocks free caption requests when you
   fetch a lot at once. Apify is a paid service (about 0.005 USD per video) that still works then, and I would
   always ask you before spending anything. Want to add it now, later, or never?" If now: open
   https://console.apify.com/sign-up , then Settings → API & Integrations → copy the Personal API token, paste it
   here, and write it into `.env` as `APIFY_TOKEN`. Never print the token back.
7. **Test run.** Transcribe one short public video with captions (any short video the user likes) and show the
   saved file path.
8. Write `SKILL_DIR/.onboarded`. Tell them how to use it: "Just paste a YouTube link and say transcribe."

## Default behaviour

When the user says "transcribe this" with a link or file: transcribe it, save it, show where it was saved and a
short preview (or the whole text if asked). Do not summarise, rewrite or turn it into anything else unless they
ask.

## YouTube: one video, several videos, a channel or a playlist

```bash
SKILL_DIR/.venv/bin/python SKILL_DIR/transcribe.py <url> [<url> ...]
```

- **Duplicates are skipped automatically.** The script checks the ledger first: `DONE` = already transcribed
  (point the user at the saved file), `NEW` = fetch. A repeat channel request fetches only the new uploads.
  Check by hand any time: `SKILL_DIR/.venv/bin/python SKILL_DIR/ledger.py check <url|id|channel-url>`.
- **Before a channel run**, run `ledger.py check <channel-url>` and tell the user how many videos are new and
  roughly how many hours of video that is. For big channels, run `transcribe.py` in the background.
- **Order it tries:** YouTube captions (free) → caption file through yt-dlp (free) → faster-whisper on this
  computer for videos with no captions (free, slow; only if installed).
- **Saved as** `TRANSCRIPTS_DIR/<channel>/YYYY-MM-DD-<videoid>-<title>.md` with the title, link, publish date,
  views, likes, length, description and the transcript. The publish date is always recorded so newer videos
  can be weighted more.
- `--timestamps` saves a separate `…-timestamps.md` with `[MM:SS]` lines, even for a video already done (captions only). `--limit N` for a sample. `--no-whisper` to skip
  speech-to-text.

**Stops: each one means stop and ask the user, never work around it.**
- *5 caption misses in a row*: YouTube is probably rate-limiting (a 429). Offer: wait an hour and retry (free),
  or Apify with the estimate the script printed and a spending cap. Only with a yes:
  `transcribe.py <urls> --method apify --cap <USD>`. A yes covers this one job only.
- *More than 10 videos need Whisper*: that is hours of computer time. Ask, then rerun with `--whisper-max N`.
- *faster-whisper or ffmpeg missing* when needed: run the install step from onboarding (ask first).

## A video or audio file on this computer

```bash
SKILL_DIR/.venv/bin/python SKILL_DIR/transcribe_local.py "<file>" [--model medium]
```
- Files over 20 minutes are first cut into 20-minute parts (lossless, saved next to the original as
  `<name>-part00`, `-part01`, …), then transcribed in order. `--no-split` skips that; `--chunk-min N` changes it.
- Output: `<name>.transcript.txt` next to the file, rewritten after each part, so a crash keeps finished parts.
- Long files: run in the background and tell the user roughly how long it will take (medium: about 40 minutes
  per 110 minutes of audio on a laptop CPU).

## Troubleshooting

- `ffmpeg: command not found` inside Claude but it works in your terminal: Claude's shell may not see Homebrew.
  Add `/opt/homebrew/bin` (Apple silicon) or `/usr/local/bin` (Intel) to PATH for the command.
- "Sign in to confirm you're not a bot" or many misses in a row: YouTube is rate-limiting. Wait, or use Apify.
- Settings live in `SKILL_DIR/.env`. "Set me up again" re-runs onboarding.
- Spending so far: `SKILL_DIR/.venv/bin/python SKILL_DIR/ledger.py stats`.
