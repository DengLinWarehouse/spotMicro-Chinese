from __future__ import annotations

from typing import Optional

from .map_registry import MapRegistry
from .models import ActionResult, ActionType, ControlMode
from .state_manager import StateManager


class AutonomyManager(object):
    def __init__(self, state_manager: StateManager, map_registry: MapRegistry):
        self._state_manager = state_manager
        self._map_registry = map_registry

    def preflight_start(self, mode: ControlMode) -> Optional[ActionResult]:
        if mode not in (ControlMode.AUTO_EXPLORE_MAPPING, ControlMode.AUTO_PATROL):
            return None

        state = self._state_manager.snapshot()
        if not state.ros_connected:
            return ActionResult(
                ActionType.START,
                False,
                "ros_not_ready",
                "automatic mode requires ROS connection before start",
                {"mode": mode.value},
            )

        if mode == ControlMode.AUTO_PATROL:
            selected_map_id = state.selected_map.map_id
            if not selected_map_id:
                return ActionResult(
                    ActionType.START,
                    False,
                    "selected_map_required",
                    "auto patrol requires a selected map before start",
                    {"mode": mode.value},
                )
            if not self._map_registry.is_map_available(selected_map_id):
                return ActionResult(
                    ActionType.START,
                    False,
                    "selected_map_unavailable",
                    "selected patrol map is unavailable on disk",
                    {"mode": mode.value, "map_id": selected_map_id},
                )

        return None
