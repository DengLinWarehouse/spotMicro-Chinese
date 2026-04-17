from __future__ import annotations

from .models import RuntimeState
from .ros_runtime_adapter import RosRuntimeAdapter
from .state_manager import StateManager


class HealthMonitor(object):
    def __init__(self, state_manager: StateManager, ros_runtime: RosRuntimeAdapter):
        self._state_manager = state_manager
        self._ros_runtime = ros_runtime

    def refresh(self):
        health = self._ros_runtime.probe_health()
        state = self._state_manager.snapshot()
        self._state_manager.set_ros_connected(health.connected)
        if not health.connected and state.runtime_state != RuntimeState.ESTOP_LATCHED:
            self._state_manager.set_fault(True, "ros_disconnected")
            self._state_manager.set_runtime_state(RuntimeState.FAULT)
        elif health.connected and state.fault_reason == "ros_disconnected":
            self._state_manager.set_fault(False, "")
            if not state.armed and state.runtime_state == RuntimeState.FAULT:
                self._state_manager.set_runtime_state(RuntimeState.READY_DISARMED)
