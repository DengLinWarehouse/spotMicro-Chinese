from __future__ import annotations

from .autonomy_manager import AutonomyManager
from .models import ActionResult, ActionType, ControlMode, ControlSource, RuntimeState
from .ros_runtime_adapter import RosRuntimeAdapter
from .state_manager import StateManager


class ActionManager(object):
    def __init__(self, state_manager: StateManager, ros_runtime: RosRuntimeAdapter, autonomy_manager: AutonomyManager):
        self._state_manager = state_manager
        self._ros_runtime = ros_runtime
        self._autonomy_manager = autonomy_manager

    def start(self) -> ActionResult:
        state = self._state_manager.snapshot()
        if state.estop_latched:
            result = ActionResult(ActionType.START, False, "estop_latched", "cannot start while estop is latched")
            self._state_manager.set_last_action(result)
            return result
        if state.fault_active:
            result = ActionResult(ActionType.START, False, "fault_active", "cannot start while fault is active")
            self._state_manager.set_last_action(result)
            return result
        if state.runtime_state in (RuntimeState.STARTING, RuntimeState.SAFE_STOPPING):
            result = ActionResult(ActionType.START, False, "busy", "cannot start during active transition")
            self._state_manager.set_last_action(result)
            return result
        preflight = self._autonomy_manager.preflight_start(state.selected_mode)
        if preflight is not None:
            self._state_manager.set_last_action(preflight)
            return preflight

        self._state_manager.set_runtime_state(RuntimeState.STARTING)
        result = self._ros_runtime.request_start(state.selected_mode)
        if result.accepted:
            self._state_manager.set_armed(True)
            self._state_manager.set_control_source(self._control_source_after_start(state.selected_mode))
            self._state_manager.set_runtime_state(self._runtime_state_after_start(state.selected_mode))
        else:
            self._state_manager.set_runtime_state(RuntimeState.READY_DISARMED)
        self._state_manager.set_last_action(result)
        return result

    def estop(self) -> ActionResult:
        result = self._ros_runtime.request_estop()
        self._state_manager.set_armed(False)
        self._state_manager.set_estop_latched(True)
        self._state_manager.set_control_source(ControlSource.ESTOP)
        self._state_manager.set_runtime_state(RuntimeState.ESTOP_LATCHED)
        self._state_manager.set_last_action(result)
        return result

    def safe_stop(self) -> ActionResult:
        state = self._state_manager.snapshot()
        if state.estop_latched:
            result = ActionResult(ActionType.SAFE_STOP, False, "estop_latched", "safe stop is blocked by estop latch")
            self._state_manager.set_last_action(result)
            return result

        self._state_manager.set_runtime_state(RuntimeState.SAFE_STOPPING)
        result = self._ros_runtime.request_safe_stop()
        if result.accepted:
            self._state_manager.set_armed(False)
            self._state_manager.set_control_source(ControlSource.NONE)
            self._state_manager.set_runtime_state(RuntimeState.READY_DISARMED)
        else:
            self._state_manager.set_fault(True, "safe_stop_failed")
            self._state_manager.set_runtime_state(RuntimeState.FAULT)
        self._state_manager.set_last_action(result)
        return result

    @staticmethod
    def _runtime_state_after_start(mode: ControlMode) -> RuntimeState:
        if mode == ControlMode.MANUAL:
            return RuntimeState.ARMED_READY
        if mode == ControlMode.MANUAL_MAPPING:
            return RuntimeState.ARMED_READY
        if mode == ControlMode.AUTO_EXPLORE_MAPPING:
            return RuntimeState.RUNNING_AUTO_EXPLORE
        return RuntimeState.RUNNING_AUTO_PATROL

    @staticmethod
    def _control_source_after_start(mode: ControlMode) -> ControlSource:
        if mode in (ControlMode.AUTO_EXPLORE_MAPPING, ControlMode.AUTO_PATROL):
            return ControlSource.AUTO
        return ControlSource.NONE
