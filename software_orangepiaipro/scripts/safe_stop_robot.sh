#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODE_CONFIG="${1:-${REPO_ROOT}/spot_micro_navigation/config/robot_mode_config.yaml}"
SESSION_NAME="${2:-}"
COMMON_RUNNER="${SCRIPT_DIR}/common_run_on_all_cores.sh"

if [[ ! -f "${MODE_CONFIG}" ]]; then
  echo "Mode config not found: ${MODE_CONFIG}" >&2
  exit 1
fi

if [[ ! -f "${COMMON_RUNNER}" ]]; then
  echo "Core affinity wrapper not found: ${COMMON_RUNNER}" >&2
  exit 1
fi

bash "${COMMON_RUNNER}" bash -c \
  "rosrun spot_micro_navigation safe_stop_robot.py --config ${MODE_CONFIG}"

if [[ -n "${SESSION_NAME}" ]]; then
  tmux kill-session -t "${SESSION_NAME}" 2>/dev/null || true
fi
