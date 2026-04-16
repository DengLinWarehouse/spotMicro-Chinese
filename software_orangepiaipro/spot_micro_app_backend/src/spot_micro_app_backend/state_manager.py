from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Optional

from .models import ActionResult, BackendState, ControlMode, ControlSource, MapSelection, RuntimeState


class StateManager(object):
    def __init__(self):
        self._lock = RLock()
        self._state = BackendState()

    def snapshot(self) -> BackendState:
        with self._lock:
            return deepcopy(self._state)

    def to_dict(self):
        return self.snapshot().to_dict()

    def set_runtime_state(self, runtime_state: RuntimeState):
        with self._lock:
            self._state.runtime_state = runtime_state

    def set_selected_mode(self, mode: ControlMode):
        with self._lock:
            self._state.selected_mode = mode

    def set_armed(self, armed: bool):
        with self._lock:
            self._state.armed = armed

    def set_estop_latched(self, latched: bool):
        with self._lock:
            self._state.estop_latched = latched

    def set_fault(self, active: bool, reason: str = ""):
        with self._lock:
            self._state.fault_active = active
            self._state.fault_reason = reason

    def set_selected_map(self, map_id: str, display_name: str):
        with self._lock:
            self._state.selected_map = MapSelection(map_id=map_id, display_name=display_name)

    def set_speed_level(self, speed_level: int):
        with self._lock:
            self._state.speed_level = max(0, int(speed_level))

    def set_control_source(self, source: ControlSource):
        with self._lock:
            self._state.current_control_source = source

    def set_ros_connected(self, connected: bool):
        with self._lock:
            self._state.ros_connected = connected

    def set_ui_connected(self, connected: bool):
        with self._lock:
            self._state.ui_connected = connected

    def mark_manual_input(self, session_id: str, timestamp_sec: float):
        with self._lock:
            self._state.last_session_id = session_id
            self._state.last_session_seen_at = timestamp_sec
            self._state.last_manual_input_at = timestamp_sec
            self._state.ui_connected = True

    def mark_session_seen(self, session_id: str, timestamp_sec: float):
        with self._lock:
            self._state.last_session_id = session_id
            self._state.last_session_seen_at = timestamp_sec
            self._state.ui_connected = True

    def set_last_action(self, result: Optional[ActionResult]):
        with self._lock:
            self._state.last_action = result
