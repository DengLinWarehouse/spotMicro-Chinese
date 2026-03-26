#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_WS="${ROS_BASE_WS:-$HOME/Desktop/SpotMicro/ros_noetic_ws}"
OVERLAY_WS="${SPOT_WS:-$HOME/Desktop/SpotMicro/spotmicro_ws}"

printf '[INFO] backup root: %s\n' "$ROOT_DIR"
printf '[INFO] base workspace: %s\n' "$BASE_WS"
printf '[INFO] overlay workspace: %s\n' "$OVERLAY_WS"

printf '\n[CHECK] python3\n'
which python3 || true
python3 -c 'import sys; print(sys.executable)' || true
python3 --version || true

printf '\n[CHECK] ROS commands\n'
command -v roscore || true
command -v rospack || true

printf '\n[CHECK] important packages\n'
dpkg -s python3-defusedxml >/dev/null 2>&1 && echo 'python3-defusedxml: installed' || echo 'python3-defusedxml: missing'
dpkg -s libi2c-dev >/dev/null 2>&1 && echo 'libi2c-dev: installed' || echo 'libi2c-dev: missing'

printf '\n[CHECK] workspace layout\n'
[ -d "$BASE_WS/src" ] && echo "base src ok: $BASE_WS/src" || echo "base src missing: $BASE_WS/src"
[ -d "$OVERLAY_WS/src" ] && echo "overlay src ok: $OVERLAY_WS/src" || echo "overlay src missing: $OVERLAY_WS/src"

printf '\n[CHECK] ros environment\n'
printf 'ROS_PACKAGE_PATH=%s\n' "${ROS_PACKAGE_PATH:-<empty>}"
printf 'CMAKE_PREFIX_PATH=%s\n' "${CMAKE_PREFIX_PATH:-<empty>}"
