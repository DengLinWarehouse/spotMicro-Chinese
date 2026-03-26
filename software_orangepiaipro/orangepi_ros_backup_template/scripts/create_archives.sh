#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_WS="${ROS_BASE_WS:-$HOME/Desktop/SpotMicro/ros_noetic_ws}"
OVERLAY_WS="${SPOT_WS:-$HOME/Desktop/SpotMicro/spotmicro_ws}"
ARCHIVE_DIR="$ROOT_DIR/archives"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$ARCHIVE_DIR"

if [ -d "$BASE_WS/src" ]; then
  tar -czf "$ARCHIVE_DIR/ros_noetic_ws_src_${STAMP}.tar.gz" -C "$BASE_WS" src
  echo "[OK] created $ARCHIVE_DIR/ros_noetic_ws_src_${STAMP}.tar.gz"
else
  echo "[WARN] skip base archive, missing $BASE_WS/src"
fi

if [ -d "$OVERLAY_WS/src" ]; then
  tar -czf "$ARCHIVE_DIR/spotmicro_ws_src_${STAMP}.tar.gz" -C "$OVERLAY_WS" src
  echo "[OK] created $ARCHIVE_DIR/spotmicro_ws_src_${STAMP}.tar.gz"
else
  echo "[WARN] skip overlay archive, missing $OVERLAY_WS/src"
fi
