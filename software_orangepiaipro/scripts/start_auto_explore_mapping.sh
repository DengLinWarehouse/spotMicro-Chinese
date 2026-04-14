#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODE_CONFIG="${1:-${REPO_ROOT}/spot_micro_navigation/config/robot_mode_config.yaml}"
SESSION_NAME="${SPOTMICRO_TMUX_SESSION:-spotmicro_auto_explore}"
COMMON_RUNNER="${SCRIPT_DIR}/common_run_on_all_cores.sh"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

build_wrapped_command() {
  local inner_cmd="$1"
  local wrapped
  printf -v wrapped "bash %q bash -c %q" "${COMMON_RUNNER}" "${inner_cmd}"
  printf '%s' "${wrapped}"
}

require_cmd tmux
require_cmd python3
require_cmd bash

if [[ ! -f "${MODE_CONFIG}" ]]; then
  echo "Mode config not found: ${MODE_CONFIG}" >&2
  exit 1
fi

if [[ ! -f "${COMMON_RUNNER}" ]]; then
  echo "Core affinity wrapper not found: ${COMMON_RUNNER}" >&2
  exit 1
fi

eval "$(python3 "${SCRIPT_DIR}/read_robot_mode_config.py" --shell auto_explore_mapping "${MODE_CONFIG}")"

if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
  echo "tmux session already exists: ${SESSION_NAME}" >&2
  echo "Close it with: tmux kill-session -t ${SESSION_NAME}" >&2
  exit 1
fi

mkdir -p "${AUTOEXP_AUTOSAVE_DIRECTORY}"

MAIN_CMD="$(build_wrapped_command "roslaunch spot_micro_navigation auto_explore_mapping.launch \
scan_topic:=${SCAN_TOPIC} \
cmd_vel_topic:=${CMD_VEL_TOPIC} \
cmd_vel_manual_topic:=${CMD_VEL_MANUAL_TOPIC} \
cmd_vel_auto_topic:=${CMD_VEL_AUTO_TOPIC} \
cmd_vel_mux_topic:=${CMD_VEL_MUX_TOPIC} \
enable_topic:=${AUTO_MODE_ENABLE_TOPIC} \
stop_topic:=${AUTO_EXPLORE_STOP_TOPIC} \
state_topic:=${AUTO_STATE_TOPIC} \
source_topic:=${CMD_VEL_SOURCE_TOPIC} \
auto_mode_enabled:=${AUTOEXP_ENABLED} \
autosave_enabled:=${AUTOEXP_AUTOSAVE_ENABLED} \
autosave_interval_sec:=${AUTOEXP_AUTOSAVE_INTERVAL_SEC} \
autosave_directory:=${AUTOEXP_AUTOSAVE_DIRECTORY} \
autosave_prefix:=${AUTOEXP_AUTOSAVE_PREFIX} \
autosave_keep_last:=${AUTOEXP_AUTOSAVE_KEEP_LAST} \
rplidar_serial_port:=${RPLIDAR_SERIAL_PORT} \
rplidar_serial_baudrate:=${RPLIDAR_SERIAL_BAUDRATE} \
rplidar_frame_id:=${RPLIDAR_FRAME_ID} \
rplidar_inverted:=${RPLIDAR_INVERTED} \
rplidar_angle_compensate:=${RPLIDAR_ANGLE_COMPENSATE}")"

KEYBOARD_CMD="$(build_wrapped_command "rosrun spot_micro_keyboard_command spotMicroKeyboardMove.py /cmd_vel:=${CMD_VEL_MANUAL_TOPIC}")"
MONITOR_CMD="$(build_wrapped_command "while ! rostopic echo ${AUTO_STATE_TOPIC}; do sleep 1; done")"

tmux new-session -d -s "${SESSION_NAME}" -n auto_explore
tmux send-keys -t "${SESSION_NAME}:0.0" "${MAIN_CMD}" C-m
tmux split-window -h -t "${SESSION_NAME}:0.0"
tmux send-keys -t "${SESSION_NAME}:0.1" "${KEYBOARD_CMD}" C-m
tmux split-window -v -t "${SESSION_NAME}:0.1"
tmux send-keys -t "${SESSION_NAME}:0.2" "${MONITOR_CMD}" C-m
tmux select-layout -t "${SESSION_NAME}:0" tiled
tmux attach -t "${SESSION_NAME}"
