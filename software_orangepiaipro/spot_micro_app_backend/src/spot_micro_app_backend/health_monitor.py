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
        self._state_manager.set_ros_connected(health.connected)
        if not health.connected and self._state_manager.snapshot().runtime_state != RuntimeState.ESTOP_LATCHED:
            self._state_manager.set_fault(True, health.message or "ros_disconnected")
        elif health.connected and self._state_manager.snapshot().fault_reason == "ros_disconnected":
            self._state_manager.set_fault(False, "")
