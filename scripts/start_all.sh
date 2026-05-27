#!/bin/bash
# Start Ibot GUI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IBOT_LOG="$ROOT/vendor/ibot.log"
mkdir -p "$ROOT/vendor"

ibot_up() {
  curl -sf "http://127.0.0.1:8765/api/status" >/dev/null 2>&1
}

if ibot_up; then
  echo "Ibot already running: http://127.0.0.1:8765"
  open "http://127.0.0.1:8765/" 2>/dev/null || true
  exit 0
fi

echo "Starting Ibot..."
cd "$ROOT"
export IBOT_GUI_REEXEC=1
PY="$ROOT/.venv/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3)"
nohup "$PY" "$ROOT/gui.py" >>"$IBOT_LOG" 2>&1 &
for _ in $(seq 1 30); do
  ibot_up && break
  sleep 1
done

if ibot_up; then
  echo "Ibot ready: http://127.0.0.1:8765"
  open "http://127.0.0.1:8765/" 2>/dev/null || true
else
  echo "Ibot failed to start. Check: $IBOT_LOG"
  exit 1
fi
