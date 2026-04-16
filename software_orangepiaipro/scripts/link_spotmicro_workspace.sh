#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_SRC_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE_ROOT="${1:-$HOME/Desktop/SpotMicro/spotmicro_ws}"
WORKSPACE_SRC="${WORKSPACE_ROOT}/src"

PACKAGES=(
  lcd_monitor
  ros-i2cpwmboard
  servo_move_keyboard
  spot_micro_app_backend
  spot_micro_joy
  spot_micro_keyboard_command
  spot_micro_launch
  spot_micro_motion_cmd
  spot_micro_navigation
  spot_micro_plot
  spot_micro_rviz
)

mkdir -p "${WORKSPACE_SRC}"

for pkg in "${PACKAGES[@]}"; do
  source_path="${REPO_SRC_ROOT}/${pkg}"
  link_path="${WORKSPACE_SRC}/${pkg}"

  if [[ ! -d "${source_path}" ]]; then
    echo "Missing source package: ${source_path}" >&2
    exit 1
  fi

  if [[ -L "${link_path}" ]]; then
    current_target="$(readlink -f "${link_path}")"
    desired_target="$(readlink -f "${source_path}")"
    if [[ "${current_target}" == "${desired_target}" ]]; then
      echo "[ok] ${pkg} already linked"
      continue
    fi
    rm "${link_path}"
  elif [[ -e "${link_path}" ]]; then
    echo "Refusing to replace existing non-symlink: ${link_path}" >&2
    echo "Please move or remove it first, then rerun this script." >&2
    exit 1
  fi

  ln -s "${source_path}" "${link_path}"
  echo "[link] ${link_path} -> ${source_path}"
done

cat <<EOF

Workspace links are ready.

Next steps on Orange Pi:
  1. source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
  2. cd ${WORKSPACE_ROOT}
  3. catkin_make

After this, edits under software_orangepiaipro will be reflected directly in spotmicro_ws/src through symlinks.
YAML-only changes do not require a rebuild when you run from the devel space, but C++/Python code changes still do.
EOF
