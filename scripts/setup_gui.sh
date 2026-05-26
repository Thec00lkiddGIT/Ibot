#!/bin/bash
# One-time setup for the native Ibot window (WebKit, not Chrome).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q pywebview
echo "Done. Run: source .venv/bin/activate && python3 gui.py"
