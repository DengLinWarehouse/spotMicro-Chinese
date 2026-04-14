#!/usr/bin/env bash
set -euo pipefail

DEFAULT_TARGET_CPU_SET="0-3"
TARGET_CPU_SET="${SPOTMICRO_TARGET_CPU_SET:-}"
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

current_cpuset_cgroup() {
  awk -F: '$2=="cpuset"{print $3; exit}' /proc/$$/cgroup 2>/dev/null
}

read_first_nonempty_file() {
  local file value
  for file in "$@"; do
    if [[ -r "${file}" ]]; then
      value="$(tr -d '[:space:]' < "${file}" 2>/dev/null || true)"
      if [[ -n "${value}" ]]; then
        printf '%s' "${value}"
        return 0
      fi
    fi
  done
  return 1
}

remove_conda_from_path() {
  local old_path entry new_path=""
  old_path="${PATH:-}"
  IFS=':' read -r -a _spotmicro_path_entries <<< "${old_path}"
  for entry in "${_spotmicro_path_entries[@]}"; do
    [[ -z "${entry}" ]] && continue
    case "${entry}" in
      *miniconda*|*anaconda*|*conda*)
        continue
        ;;
    esac
    if [[ -z "${new_path}" ]]; then
      new_path="${entry}"
    else
      new_path="${new_path}:${entry}"
    fi
  done
  if [[ -n "${new_path}" ]]; then
    PATH="${new_path}"
  fi
}

detect_target_cpu_set() {
  local cpuset_group

  if [[ -n "${TARGET_CPU_SET}" ]]; then
    printf '%s' "${TARGET_CPU_SET}"
    return 0
  fi

  cpuset_group="$(current_cpuset_cgroup || true)"
  if [[ -n "${cpuset_group}" ]]; then
    if read_first_nonempty_file \
      "/sys/fs/cgroup/cpuset${cpuset_group}/cpuset.cpus" \
      "/sys/fs/cgroup/cpuset${cpuset_group}/cpuset.effective_cpus" \
      "/sys/fs/cgroup/cpuset${cpuset_group}/cpuset.cpus.effective"
    then
      return 0
    fi
  fi

  if read_first_nonempty_file \
    "/sys/fs/cgroup/cpuset/cpuset.cpus" \
    "/sys/fs/cgroup/cpuset/cpuset.effective_cpus" \
    "/sys/fs/cgroup/cpuset.cpus.effective" \
    "/sys/fs/cgroup/cpuset.cpus"
  then
    return 0
  fi

  printf '%s' "${DEFAULT_TARGET_CPU_SET}"
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
  local ros_setup="${SPOTMICRO_ROS_SETUP_SCRIPT:-}"
  local base_setup="${SPOTMICRO_BASE_SETUP_SCRIPT:-}"
  local overlay_setup="${SPOTMICRO_OVERLAY_SETUP_SCRIPT:-${SPOTMICRO_SETUP_SCRIPT:-}}"

  if [[ -z "${ros_setup}" ]]; then
    for candidate in \
      "/opt/ros/${ROS_DISTRO_NAME}/setup.bash" \
      "${HOME}/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash" \
      "${HOME}/catkin_ws/devel/setup.bash"
    do
      if [[ -f "${candidate}" ]]; then
        ros_setup="${candidate}"
        break
      fi
    done
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

  if [[ -n "${ros_setup}" && -n "${base_setup}" && "${ros_setup}" == "${base_setup}" ]]; then
    base_setup=""
  fi

  if [[ -z "${ros_setup}" || ! -f "${ros_setup}" ]]; then
    if [[ -n "${base_setup}" && -f "${base_setup}" ]]; then
      echo "[WARN] ROS setup script not found: ${ros_setup:-<unset>}" >&2
      echo "[WARN] Falling back to base workspace setup: ${base_setup}" >&2
      ros_setup=""
    else
      echo "[ERROR] ROS setup script not found: ${ros_setup:-<unset>}" >&2
      echo "        Set SPOTMICRO_ROS_SETUP_SCRIPT or provide a valid base workspace setup script." >&2
      exit 1
    fi
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

  remove_conda_from_path
  unset CONDA_PREFIX
  unset CONDA_DEFAULT_ENV
  unset CONDA_PROMPT_MODIFIER
  unset CONDA_SHLVL
  unset CONDA_EXE
  unset CONDA_PYTHON_EXE
  unset _CE_CONDA
  unset _CE_M

  unset PYTHONPATH
  unset PYTHONHOME
  unset LD_LIBRARY_PATH

  if [[ -n "${ros_setup}" ]]; then
    # shellcheck disable=SC1090
    source "${ros_setup}"
  fi
  if [[ -n "${base_setup}" ]]; then
    # shellcheck disable=SC1090
    source "${base_setup}"
  fi
  # shellcheck disable=SC1090
  source "${overlay_setup}"
}

main() {
  local cpuset_group

  require_cmd taskset
  require_cmd bash

  if [[ $# -lt 1 ]]; then
    echo "Usage: $(basename "$0") <command> [args...]" >&2
    exit 1
  fi

  TARGET_CPU_SET="$(detect_target_cpu_set)"
  cpuset_group="$(current_cpuset_cgroup || true)"
  ensure_all_cores "$@"
  prepare_ros_env

  echo "[INFO] shell pid: $$"
  echo "[INFO] shell affinity: $(current_affinity)"
  echo "[INFO] target cpu set: ${TARGET_CPU_SET}"
  echo "[INFO] cpuset cgroup: ${cpuset_group:-/}"
  echo "[INFO] running command: $*"

  exec "$@"
}

main "$@"
