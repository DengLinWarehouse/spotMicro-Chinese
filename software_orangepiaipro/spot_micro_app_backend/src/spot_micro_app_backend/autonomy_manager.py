from __future__ import annotations

from typing import Optional

from .map_registry import MapRegistry
from .models import ActionResult, ActionType, ControlMode
from .ros_runtime_adapter import PatrolConfig
from .state_manager import StateManager


class AutonomyManager(object):
    def __init__(self, state_manager: StateManager, map_registry: MapRegistry, dry_run: bool, patrol_config: PatrolConfig):
        self._state_manager = state_manager
        self._map_registry = map_registry
        self._dry_run = bool(dry_run)
        self._patrol_config = patrol_config

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
            if not self._dry_run and not bool(self._patrol_config.live_execution_enabled):
                return ActionResult(
                    ActionType.START,
                    False,
                    "live_patrol_disabled",
                    "live random patrol is disabled until a safer navigation layer is implemented",
                    {"mode": mode.value},
                )
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
