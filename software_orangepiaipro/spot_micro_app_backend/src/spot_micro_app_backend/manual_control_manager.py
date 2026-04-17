from __future__ import annotations

from .models import ControlMode, ControlSource, ManualIntent, RuntimeState
from .ros_runtime_adapter import RosRuntimeAdapter
from .session_watchdog import SessionWatchdog
from .state_manager import StateManager


class ManualControlManager(object):
    def __init__(self, state_manager: StateManager, ros_runtime: RosRuntimeAdapter, watchdog: SessionWatchdog):
        self._state_manager = state_manager
        self._ros_runtime = ros_runtime
        self._watchdog = watchdog

    def submit_intent(self, intent: ManualIntent):
        state = self._state_manager.snapshot()
        if state.estop_latched or state.fault_active or not state.armed:
            return False
        if state.selected_mode not in (ControlMode.MANUAL, ControlMode.MANUAL_MAPPING, ControlMode.AUTO_EXPLORE_MAPPING):
            return False

        self._watchdog.note_manual_input(intent.session_id, intent.timestamp_sec)
        result = self._ros_runtime.publish_manual_intent(intent, state.speed_level, state.selected_mode)
        self._state_manager.set_last_action(result)
        if not result.accepted:
            return False

        self._state_manager.set_control_source(ControlSource.MANUAL)
        if intent.is_neutral():
            self._state_manager.set_runtime_state(RuntimeState.ARMED_READY)
        elif state.selected_mode == ControlMode.MANUAL:
            self._state_manager.set_runtime_state(RuntimeState.RUNNING_MANUAL)
        else:
            self._state_manager.set_runtime_state(RuntimeState.RUNNING_MANUAL_MAPPING)
        return True

    def handle_timeout(self):
        state = self._state_manager.snapshot()
        if state.current_control_source != ControlSource.MANUAL:
            return
        if not self._watchdog.manual_input_expired():
            return

        neutral_intent = ManualIntent(
            forward_axis=0.0,
            turn_axis=0.0,
            timestamp_sec=state.last_manual_input_at,
            session_id=state.last_session_id or "timeout",
        )
        mode = state.selected_mode
        self._ros_runtime.publish_manual_intent(neutral_intent, state.speed_level, mode)
        self._state_manager.set_control_source(ControlSource.NONE)
        if state.armed:
            self._state_manager.set_runtime_state(RuntimeState.ARMED_READY)
