#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_WS="${ROS_BASE_WS:-$HOME/Desktop/SpotMicro/ros_noetic_ws}"
DST_DIR="$ROOT_DIR/workspaces/ros_noetic_ws/src"

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

if [ ! -d "$BASE_WS/src" ]; then
  echo "[ERROR] missing base workspace: $BASE_WS/src" >&2
  exit 1
fi

printf '[INFO] export %s -> %s\n' "$BASE_WS/src" "$DST_DIR"
sync_dir "$BASE_WS/src" "$DST_DIR"

echo "[OK] ros_noetic_ws source exported"
