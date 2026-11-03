#!/usr/bin/env bash
# Installs /transcribe as a Claude Code skill in ~/.claude/skills/transcribe
set -euo pipefail
REPO="https://github.com/dlinyvr/local-transcribe.git"
DEST="$HOME/.claude/skills/transcribe"
mkdir -p "$HOME/.claude/skills"
if [ -d "$DEST/.git" ]; then
  git -C "$DEST" pull -q && echo "Updated /transcribe."
elif [ -e "$DEST" ]; then
  echo "Something already exists at $DEST. Move or rename it, then run this again."; exit 1
else
  git clone -q "${SKILLSHARE_LOCAL_SOURCE:-$REPO}" "$DEST" && echo "Installed /transcribe."
fi
echo "Next: open Claude Code and say \"transcribe https://youtu.be/<any video>\". The first run walks you through setup."
