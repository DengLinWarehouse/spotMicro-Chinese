#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODE_CONFIG="${1:-${REPO_ROOT}/spot_micro_navigation/config/robot_mode_config.yaml}"
SESSION_NAME="${SPOTMICRO_TMUX_SESSION:-spotmicro_auto_explore}"
COMMON_RUNNER="${SCRIPT_DIR}/common_run_on_all_cores.sh"
STOP_SCRIPT="${SCRIPT_DIR}/safe_stop_robot.sh"
RUN_TS="$(date +%Y%m%d_%H%M%S)"
RUN_ID="auto_explore_${RUN_TS}"
RUNTIME_EXPORTS=""

append_runtime_export() {
  local name="$1"
  local value="$2"
  local quoted
  printf -v quoted "%q" "${value}"
  RUNTIME_EXPORTS+="export ${name}=${quoted}; "
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

build_wrapped_command() {
  local inner_cmd="$1"
  local wrapped
  printf -v wrapped "bash %q bash -c %q" "${COMMON_RUNNER}" "${RUNTIME_EXPORTS}${inner_cmd}"
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

if [[ ! -f "${STOP_SCRIPT}" ]]; then
  echo "Safe stop script not found: ${STOP_SCRIPT}" >&2
  exit 1
fi

eval "$(python3 "${SCRIPT_DIR}/read_robot_mode_config.py" --shell auto_explore_mapping "${MODE_CONFIG}")"

if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
  echo "tmux session already exists: ${SESSION_NAME}" >&2
  echo "Close it with: tmux kill-session -t ${SESSION_NAME}" >&2
  exit 1
fi

mkdir -p "${AUTOEXP_AUTOSAVE_DIRECTORY}"

if [[ "${LOGGING_ENABLED}" == "true" ]]; then
  RUN_LOG_DIR="${LOGGING_ROOT_DIRECTORY}/${RUN_ID}"
  mkdir -p "${RUN_LOG_DIR}/pane_logs" "${RUN_LOG_DIR}/metadata"
  append_runtime_export "SPOTMICRO_RUN_ID" "${RUN_ID}"
  append_runtime_export "SPOTMICRO_RUN_LOG_DIR" "${RUN_LOG_DIR}"

  if [[ "${LOGGING_ROS_LOG_ENABLED}" == "true" ]]; then
    mkdir -p "${RUN_LOG_DIR}/rosconsole"
    append_runtime_export "ROS_LOG_DIR" "${RUN_LOG_DIR}/rosconsole"
  fi

  {
    echo "run_id=${RUN_ID}"
    echo "mode=auto_explore_mapping"
    echo "session_name=${SESSION_NAME}"
    echo "mode_config=${MODE_CONFIG}"
    echo "run_log_dir=${RUN_LOG_DIR}"
    echo "autosave_directory=${AUTOEXP_AUTOSAVE_DIRECTORY}"
    echo "rosbag_enabled=${LOGGING_ROSBAG_ENABLED}"
    echo "rosbag_topics=${LOGGING_ROSBAG_TOPICS}"
    echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "${RUN_LOG_DIR}/metadata/session.env"
fi

MAIN_CMD="$(build_wrapped_command "roslaunch spot_micro_navigation auto_explore_mapping.launch \
scan_topic:=${SCAN_TOPIC} \
cmd_vel_topic:=${CMD_VEL_TOPIC} \
cmd_vel_manual_topic:=${CMD_VEL_MANUAL_TOPIC} \
cmd_vel_auto_topic:=${CMD_VEL_AUTO_TOPIC} \
cmd_vel_mux_topic:=${CMD_VEL_MUX_TOPIC} \
stand_topic:=${STAND_TOPIC} \
walk_topic:=${WALK_TOPIC} \
idle_topic:=${IDLE_TOPIC} \
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
startup_idle_enabled:=${LIFECYCLE_STARTUP_IDLE_ENABLED} \
startup_idle_delay_sec:=${LIFECYCLE_STARTUP_IDLE_DELAY_SEC} \
startup_stand_delay_sec:=${LIFECYCLE_STARTUP_STAND_DELAY_SEC} \
startup_walk_delay_sec:=${LIFECYCLE_STARTUP_WALK_DELAY_SEC} \
startup_auto_enable_delay_sec:=${LIFECYCLE_STARTUP_AUTO_ENABLE_DELAY_SEC} \
startup_zero_cmd_duration_sec:=${LIFECYCLE_STARTUP_ZERO_CMD_DURATION_SEC} \
shutdown_zero_cmd_duration_sec:=${LIFECYCLE_SHUTDOWN_ZERO_CMD_DURATION_SEC} \
shutdown_stand_hold_sec:=${LIFECYCLE_SHUTDOWN_STAND_HOLD_SEC} \
pulse_count:=${LIFECYCLE_PULSE_COUNT} \
pulse_interval_sec:=${LIFECYCLE_PULSE_INTERVAL_SEC} \
rplidar_serial_port:=${RPLIDAR_SERIAL_PORT} \
rplidar_serial_baudrate:=${RPLIDAR_SERIAL_BAUDRATE} \
rplidar_frame_id:=${RPLIDAR_FRAME_ID} \
rplidar_inverted:=${RPLIDAR_INVERTED} \
rplidar_angle_compensate:=${RPLIDAR_ANGLE_COMPENSATE}")"

KEYBOARD_CMD="$(build_wrapped_command "rosrun spot_micro_keyboard_command spotMicroKeyboardMove.py /cmd_vel:=${CMD_VEL_MANUAL_TOPIC}")"
MONITOR_CMD="$(build_wrapped_command "while ! rostopic echo ${AUTO_STATE_TOPIC}; do sleep 1; done")"
ROSBAG_CMD=""

if [[ "${LOGGING_ENABLED}" == "true" && "${LOGGING_ROSBAG_ENABLED}" == "true" ]]; then
  mkdir -p "${RUN_LOG_DIR}/rosbag"
  ROSBAG_CMD="$(build_wrapped_command "command -v rosbag >/dev/null 2>&1 || { echo '[ERROR] Missing required command: rosbag' >&2; exit 1; }; exec rosbag record --output-prefix ${RUN_LOG_DIR}/rosbag/${LOGGING_ROSBAG_OUTPUT_PREFIX}_${RUN_ID} ${LOGGING_ROSBAG_TOPICS}")"
fi

printf -v STOP_CMD "bash %q %q %q" "${STOP_SCRIPT}" "${MODE_CONFIG}" "${SESSION_NAME}"

tmux new-session -d -s "${SESSION_NAME}" -n auto_explore
tmux set-option -t "${SESSION_NAME}" remain-on-exit on
tmux bind-key -T root -n C-c if-shell -F "#{==:#{session_name},${SESSION_NAME}}" "run-shell '${STOP_CMD}'" "send-keys C-c"
tmux send-keys -t "${SESSION_NAME}:0.0" "${MAIN_CMD}" C-m
tmux split-window -h -t "${SESSION_NAME}:0.0"
tmux send-keys -t "${SESSION_NAME}:0.1" "${KEYBOARD_CMD}" C-m
tmux split-window -v -t "${SESSION_NAME}:0.1"
tmux send-keys -t "${SESSION_NAME}:0.2" "${MONITOR_CMD}" C-m
if [[ -n "${ROSBAG_CMD}" ]]; then
  tmux split-window -v -t "${SESSION_NAME}:0.0"
  tmux send-keys -t "${SESSION_NAME}:0.3" "${ROSBAG_CMD}" C-m
fi
if [[ "${LOGGING_ENABLED}" == "true" && "${LOGGING_PANE_CAPTURE_ENABLED}" == "true" ]]; then
  tmux pipe-pane -o -t "${SESSION_NAME}:0.0" "cat >> '${RUN_LOG_DIR}/pane_logs/main.log'"
  tmux pipe-pane -o -t "${SESSION_NAME}:0.1" "cat >> '${RUN_LOG_DIR}/pane_logs/keyboard.log'"
  tmux pipe-pane -o -t "${SESSION_NAME}:0.2" "cat >> '${RUN_LOG_DIR}/pane_logs/monitor.log'"
  if [[ -n "${ROSBAG_CMD}" ]]; then
    tmux pipe-pane -o -t "${SESSION_NAME}:0.3" "cat >> '${RUN_LOG_DIR}/pane_logs/rosbag.log'"
  fi
fi
tmux select-layout -t "${SESSION_NAME}:0" tiled
if [[ "${LOGGING_ENABLED}" == "true" ]]; then
  echo "[INFO] runtime logs: ${RUN_LOG_DIR}"
fi
tmux attach -t "${SESSION_NAME}"
