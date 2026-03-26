#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OVERLAY_WS="${SPOT_WS:-$HOME/Desktop/SpotMicro/spotmicro_ws}"
DST_DIR="$ROOT_DIR/workspaces/spotmicro_ws/src"

sync_dir() {
  local src="$1"
  local dst="$2"
  mkdir -p "$dst"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$src/" "$dst/"
  else
    find "$dst" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -exec rm -rf {} +
    cp -a "$src/." "$dst/"
  fi
}

if [ ! -d "$OVERLAY_WS/src" ]; then
  echo "[ERROR] missing overlay workspace: $OVERLAY_WS/src" >&2
  exit 1
fi

printf '[INFO] export %s -> %s\n' "$OVERLAY_WS/src" "$DST_DIR"
sync_dir "$OVERLAY_WS/src" "$DST_DIR"

echo "[OK] spotmicro_ws source exported"
