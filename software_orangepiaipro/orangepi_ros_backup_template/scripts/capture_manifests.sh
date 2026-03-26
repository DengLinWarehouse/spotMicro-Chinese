#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$ROOT_DIR/manifests"
mkdir -p "$OUT_DIR"

{
  echo "timestamp=$(date -Iseconds)"
  echo "hostname=$(hostname)"
  echo "kernel=$(uname -a)"
  if command -v lsb_release >/dev/null 2>&1; then
    lsb_release -a 2>/dev/null || true
  fi
  echo "python3=$(command -v python3 || true)"
  python3 --version 2>/dev/null || true
  echo "gcc=$(command -v gcc || true)"
  gcc --version 2>/dev/null | head -n 1 || true
  echo "cmake=$(command -v cmake || true)"
  cmake --version 2>/dev/null | head -n 1 || true
  echo "git=$(command -v git || true)"
  git --version 2>/dev/null || true
} > "$OUT_DIR/system-info.txt"

apt-mark showmanual | sort > "$OUT_DIR/apt-manual.txt"

if python3 -m pip --version >/dev/null 2>&1; then
  python3 -m pip freeze > "$OUT_DIR/python3-freeze.txt"
else
  echo '# pip not available under current python3' > "$OUT_DIR/python3-freeze.txt"
fi

{
  echo "ROS_PACKAGE_PATH=${ROS_PACKAGE_PATH:-}"
  echo "CMAKE_PREFIX_PATH=${CMAKE_PREFIX_PATH:-}"
  echo "ROS_MASTER_URI=${ROS_MASTER_URI:-}"
  echo "PYTHONPATH=${PYTHONPATH:-}"
} > "$OUT_DIR/ros-environment.txt"

echo '[OK] manifests updated'
