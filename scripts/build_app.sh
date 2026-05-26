#!/bin/bash
# Build Ibot.app for distribution (optionally bundles .venv for pywebview).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE="${RELEASE:-0}"
APP="$ROOT/Ibot.app"
DESKTOP_APP="$HOME/Desktop/Ibot.app"
MACOS="$APP/Contents/MacOS"
RES="$APP/Contents/Resources"
VERSION="${IBOT_VERSION:-1.0.0}"

rm -rf "$APP"
mkdir -p "$MACOS" "$RES"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>Ibot</string>
  <key>CFBundleIdentifier</key>
  <string>com.ibot.app</string>
  <key>CFBundleName</key>
  <string>Ibot</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${VERSION}</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>CFBundleIconFile</key>
  <string>icon</string>
</dict>
</plist>
PLIST

cat > "$MACOS/Ibot" <<'LAUNCHER'
#!/bin/bash
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BUNDLE_ROOT="$(cd "$(dirname "$0")/../Resources/Ibot" && pwd)"
PARENT="$(dirname "$APP_DIR")"
if [ -f "$PARENT/gui.py" ]; then
  ROOT="$PARENT"
  export IBOT_APP_BUNDLE=0
else
  ROOT="$BUNDLE_ROOT"
  export IBOT_APP_BUNDLE=1
  export IBOT_APP_PATH="$APP_DIR"
fi
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export IBOT_GUI_LAUNCHED=1
export IBOT_GUI_REEXEC=1
PY="/usr/bin/python3"
if [ -x "$ROOT/.venv/bin/python3" ]; then
  PY="$ROOT/.venv/bin/python3"
elif ! "$PY" -c "import webview" 2>/dev/null; then
  for candidate in \
    /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3; do
    if [ -x "$candidate" ] && "$candidate" -c "import webview" 2>/dev/null; then
      PY="$candidate"
      break
    fi
  done
fi
exec "$PY" "$ROOT/gui.py"
LAUNCHER
chmod +x "$MACOS/Ibot"

ICON_SRC="$ROOT/ibot/gui/assets/icon.png"
if [ -f "$ICON_SRC" ]; then
  ICONSET="$APP/Contents/Resources/icon.iconset"
  mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z "$double" "$double" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/icon.icns"
  rm -rf "$ICONSET"
fi

RSYNC_EXCLUDES=(
  --exclude '__pycache__'
  --exclude '*.pyc'
  --exclude '.git'
  --exclude 'Ibot.app'
  --exclude 'dist'
  --exclude '.env'
  --exclude '.state.json'
  --exclude '.gui_stats.json'
  --exclude '.gui_settings.json'
)

if [ "$RELEASE" = "1" ]; then
  if [ ! -x "$ROOT/.venv/bin/python3" ]; then
    echo "Release build needs .venv with pywebview. Run: ./scripts/setup_gui.sh" >&2
    exit 1
  fi
  "$ROOT/.venv/bin/python3" -c "import webview" 2>/dev/null || {
    echo "Release build needs pywebview in .venv. Run: ./scripts/setup_gui.sh" >&2
    exit 1
  }
  rsync -a "${RSYNC_EXCLUDES[@]}" "$ROOT/" "$RES/Ibot/"
  rsync -a "$ROOT/.venv/" "$RES/Ibot/.venv/"
else
  RSYNC_EXCLUDES+=(--exclude '.venv')
  rsync -a "${RSYNC_EXCLUDES[@]}" "$ROOT/" "$RES/Ibot/"
fi

if [ "$RELEASE" != "1" ]; then
  rm -rf "$DESKTOP_APP"
  cp -R "$APP" "$DESKTOP_APP"
  echo "Built: $APP"
  echo "Also on Desktop: $DESKTOP_APP"
else
  echo "Built release app: $APP (v${VERSION})"
fi

echo "Run: python3 gui.py   (or double-click Ibot.app)"
