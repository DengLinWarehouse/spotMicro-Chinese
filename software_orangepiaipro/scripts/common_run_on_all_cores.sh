#!/usr/bin/env bash
set -euo pipefail

TARGET_CPU_SET="${SPOTMICRO_TARGET_CPU_SET:-0-3}"
ROS_DISTRO_NAME="${ROS_DISTRO:-noetic}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Missing required command: $1" >&2
    exit 1
  fi
}

current_affinity() {
  taskset -pc $$ 2>/dev/null | awk -F': ' '{print $2}'
}

ensure_all_cores() {
  local current
  current="$(current_affinity || true)"

  if [[ "${current}" == "${TARGET_CPU_SET}" ]]; then
    return 0
  fi

  if [[ "${SPOTMICRO_AFFINITY_REEXEC:-0}" == "1" ]]; then
    echo "[ERROR] Failed to switch shell affinity to ${TARGET_CPU_SET}; current affinity is ${current:-unknown}" >&2
    exit 1
  fi

  echo "[INFO] Re-exec shell affinity from ${current:-unknown} to ${TARGET_CPU_SET}"
  export SPOTMICRO_AFFINITY_REEXEC=1
  exec taskset -c "${TARGET_CPU_SET}" bash "$0" "$@"
}

prepare_ros_env() {
  local ros_setup="/opt/ros/${ROS_DISTRO_NAME}/setup.bash"
  local base_setup="${SPOTMICRO_BASE_SETUP_SCRIPT:-}"
  local overlay_setup="${SPOTMICRO_OVERLAY_SETUP_SCRIPT:-${SPOTMICRO_SETUP_SCRIPT:-}}"

  if [[ ! -f "${ros_setup}" ]]; then
    echo "[ERROR] ROS setup script not found: ${ros_setup}" >&2
    exit 1
  fi

  if [[ -z "${base_setup}" ]]; then
    for candidate in \
      "${HOME}/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash" \
      "${HOME}/catkin_ws/devel/setup.bash"
    do
      if [[ -f "${candidate}" ]]; then
        base_setup="${candidate}"
        break
      fi
    done
  fi

  if [[ -z "${overlay_setup}" ]]; then
    for candidate in \
      "${HOME}/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash" \
      "${HOME}/spotmicro_ws/devel/setup.bash"
    do
      if [[ -f "${candidate}" ]]; then
        overlay_setup="${candidate}"
        break
      fi
    done
  fi

  if [[ -n "${base_setup}" && ! -f "${base_setup}" ]]; then
    echo "[ERROR] Base workspace setup script not found: ${base_setup}" >&2
    exit 1
  fi

  if [[ -z "${overlay_setup}" || ! -f "${overlay_setup}" ]]; then
    echo "[ERROR] SpotMicro workspace setup script not found." >&2
    echo "        Set SPOTMICRO_OVERLAY_SETUP_SCRIPT or create ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash." >&2
    exit 1
  fi

  if command -v conda >/dev/null 2>&1; then
    conda deactivate 2>/dev/null || true
  fi

  unset PYTHONPATH
  unset PYTHONHOME
  unset LD_LIBRARY_PATH

  # shellcheck disable=SC1090
  source "${ros_setup}"
  if [[ -n "${base_setup}" ]]; then
    # shellcheck disable=SC1090
    source "${base_setup}"
  fi
  # shellcheck disable=SC1090
  source "${overlay_setup}"
}

main() {
  require_cmd taskset
  require_cmd bash

  if [[ $# -lt 1 ]]; then
    echo "Usage: $(basename "$0") <command> [args...]" >&2
    exit 1
  fi

  ensure_all_cores "$@"
  prepare_ros_env

  echo "[INFO] shell pid: $$"
  echo "[INFO] shell affinity: $(current_affinity)"
  echo "[INFO] running command: $*"

  exec "$@"
}

main "$@"
