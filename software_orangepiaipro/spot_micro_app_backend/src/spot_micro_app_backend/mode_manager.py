from __future__ import annotations

from .models import ActionResult, ActionType, ControlMode, ControlSource, RuntimeState
from .state_manager import StateManager


class ModeManager(object):
    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    def select_mode(self, mode: ControlMode) -> ActionResult:
        state = self._state_manager.snapshot()
        if state.estop_latched:
            return ActionResult(
                ActionType.SELECT_MODE, False, "estop_latched", "cannot change mode while estop is latched"
            )
        if state.fault_active:
            return ActionResult(
                ActionType.SELECT_MODE, False, "fault_active", "cannot change mode while fault is active"
            )
        if state.runtime_state in (RuntimeState.STARTING, RuntimeState.SAFE_STOPPING):
            return ActionResult(
                ActionType.SELECT_MODE, False, "busy", "cannot change mode during active transition"
            )

        self._state_manager.set_armed(False)
        self._state_manager.set_control_source(ControlSource.NONE)
        self._state_manager.set_selected_mode(mode)
        self._state_manager.set_runtime_state(RuntimeState.READY_DISARMED)
        result = ActionResult(ActionType.SELECT_MODE, True, "mode_selected", "mode updated", {"mode": mode.value})
        self._state_manager.set_last_action(result)
        return result
