# local-transcribe

A Claude Code skill that turns YouTube videos and files on your computer into text, for free in most cases.

## What it does

Paste a YouTube link (a video, a Short, a whole channel or a playlist) or point it at a video or audio file on your
computer, and say "transcribe this". It saves a tidy markdown file for each video with the title, link, publish
date, views and the full transcript. It uses YouTube's own captions first, which is free and instant. When a video
has no captions, it can turn the audio into text on your own computer, also free. It remembers everything it has
done, so it never transcribes the same video twice.

- **You give it:** a YouTube link or a file path.
- **You get:** `YYYY-MM-DD-<videoid>-<title>.md` per video, in one folder per channel (you choose where), or
  `<name>.transcript.txt` next to a local file.

## Install (one line)

```bash
curl -fsSL https://raw.githubusercontent.com/dlinyvr/local-transcribe/main/install.sh | bash
```

Then open Claude Code anywhere and say: **"transcribe https://youtu.be/…"** (any video).

## What happens the first time

You don't need to set anything up yourself. On the first run Claude walks you through it and **asks before
installing anything**:

1. Checks you have Python, and makes a private Python folder inside the skill so nothing else on your computer changes.
2. Installs two small free tools for YouTube captions (it asks first).
3. Asks where you want your transcripts saved (it suggests `~/transcripts/youtube`).
4. Asks if you want speech-to-text on your computer for videos without captions and for your own files. If yes,
   it explains the model sizes and recommends one (faster-whisper, medium), then installs it and ffmpeg (asking
   first).
5. Asks if you want the optional paid fallback (Apify). Most people can skip it.
6. Does a short test run so you can see it working.

Setup takes a few minutes. After that you just paste links.

## What it costs

| Service | Needed? | Cost | Notes |
|---|---|---|---|
| YouTube captions (youtube-transcript-api, yt-dlp) | Yes | Free | Works for most videos |
| faster-whisper + ffmpeg | Optional | Free | Runs on your computer. Medium model: about 1.5 GB download once, and about 40 minutes per 110 minutes of audio on a laptop |
| Apify | Optional | About 0.005 USD per video | Only when YouTube blocks free requests, and only after you say yes. You set a spending cap |
| Claude Code | Yes | Your Claude plan | |

## Things you can say

- "transcribe https://youtu.be/…"
- "transcribe this channel https://www.youtube.com/@…" (it tells you how many new videos there are first)
- "transcribe ~/Downloads/interview.mp4"
- "transcribe this with timestamps"
- "set me up again"

## Settings

All settings live in `~/.claude/skills/transcribe/.env` (the first run creates it with you). See `.env.example`.

## Update

Run the install line again.

## Changelog

- v1.0.0 (2026-11-03): first release.

MIT licensed (see LICENSE).
