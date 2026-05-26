#!/bin/bash
# Build Ibot.app on the Desktop (double-click to open native GUI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Ibot.app"
DESKTOP_APP="$HOME/Desktop/Ibot.app"
MACOS="$APP/Contents/MacOS"
RES="$APP/Contents/Resources"

rm -rf "$APP"
mkdir -p "$MACOS" "$RES"

cat > "$APP/Contents/Info.plist" <<'PLIST'
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
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
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
# Dev: Ibot.app lives inside the project folder - use live source.
PARENT="$(dirname "$APP_DIR")"
if [ -f "$PARENT/gui.py" ]; then
  ROOT="$PARENT"
else
  ROOT="$BUNDLE_ROOT"
fi
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export IBOT_GUI_LAUNCHED=1
export IBOT_GUI_REEXEC=1
PY="/usr/bin/python3"
if [ -x "$ROOT/.venv/bin/python3" ]; then
  PY="$ROOT/.venv/bin/python3"
elif ! "$PY" -c "import tkinter" 2>/dev/null; then
  for candidate in \
    /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3; do
    if [ -x "$candidate" ] && "$candidate" -c "import tkinter" 2>/dev/null; then
      PY="$candidate"
      break
    fi
  done
fi
exec "$PY" "$ROOT/gui.py"
LAUNCHER
chmod +x "$MACOS/Ibot"

ICON_SRC="$ROOT/ibot/gui/assets/icon.png"
ICON_GIF="$ROOT/ibot/gui/assets/icon.gif"
if [ -f "$ICON_SRC" ] && [ ! -f "$ICON_GIF" ]; then
  sips -s format gif "$ICON_SRC" --out "$ICON_GIF" >/dev/null 2>&1 || true
fi
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

# Copy project into app bundle (includes .env)
rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.venv' \
  --exclude '.git' \
  "$ROOT/" "$RES/Ibot/"

# Symlink/copy app to Desktop for easy access
rm -rf "$DESKTOP_APP"
cp -R "$APP" "$DESKTOP_APP"

echo "Built: $APP"
echo "Also on Desktop: $DESKTOP_APP"
echo "Run: python3 gui.py   (or double-click Ibot.app)"
