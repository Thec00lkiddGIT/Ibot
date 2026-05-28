#!/bin/bash
# Build a release DMG for Ibot (self-contained .app with bundled .venv).
#
# Release checklist:
#   - scripts/hub/ has default echo + calc (merged into user hub on launch)
#   - Wipe activity log so the dashboard feed starts clean
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
VERSION="${IBOT_VERSION:-1.0.5}"
DMG_NAME="Ibot-${VERSION}.dmg"
STAGING="$DIST/dmg-staging"

cd "$ROOT"

ACTIVITY_LOG="$HOME/Library/Application Support/Ibot/activity.log"
if [ -f "$ACTIVITY_LOG" ]; then
  echo "Wiping activity log: $ACTIVITY_LOG"
  : >"$ACTIVITY_LOG"
fi

if [ ! -d .venv ]; then
  echo "Setting up GUI dependencies..."
  ./scripts/setup_gui.sh
fi

echo "Building Ibot.app (release)..."
RELEASE=1 IBOT_VERSION="$VERSION" ./scripts/build_app.sh

rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$ROOT/Ibot.app" "$STAGING/"
ln -sf /Applications "$STAGING/Applications"

mkdir -p "$DIST"
rm -f "$DIST/$DMG_NAME" "$DIST/Ibot.dmg"

echo "Creating DMG..."
hdiutil create \
  -volname "Ibot ${VERSION}" \
  -srcfolder "$STAGING" \
  -ov \
  -format UDZO \
  "$DIST/$DMG_NAME"

rm -rf "$STAGING"

# Stable alias for CI / release uploads
ln -sf "$DMG_NAME" "$DIST/Ibot.dmg"

echo ""
echo "Done: $DIST/$DMG_NAME"
ls -lh "$DIST/$DMG_NAME"
