from __future__ import annotations

import time

from .action_manager import ActionManager
from .autonomy_manager import AutonomyManager
from .health_monitor import HealthMonitor
from .manual_control_manager import ManualControlManager
from .map_registry import MapRegistry, MapStorageConfig
from .mode_manager import ModeManager
from .models import ActionResult, ActionType, ControlMode, ManualIntent
from .ros_runtime_adapter import DryRunRosRuntimeAdapter, RuntimeAdapterConfig, TopicRosRuntimeAdapter
from .session_watchdog import SessionWatchdog
from .state_manager import StateManager
from .status_gateway import StatusGateway


class SpotMicroAppBackend(object):
    def __init__(self, config: RuntimeAdapterConfig, map_storage_config: MapStorageConfig):
        self.config = config
        self.state_manager = StateManager()
        if config.dry_run:
            self.ros_runtime = DryRunRosRuntimeAdapter(config)
        else:
            self.ros_runtime = TopicRosRuntimeAdapter(config)
        self.watchdog = SessionWatchdog(
            self.state_manager,
            manual_input_timeout_sec=config.manual_input_timeout_sec,
            session_timeout_sec=config.session_timeout_sec,
        )
        self.mode_manager = ModeManager(self.state_manager)
        self.map_registry = MapRegistry(
            self.state_manager,
            storage_config=map_storage_config,
            map_topic=config.topics.map_topic,
            dry_run=config.dry_run,
        )
        self.autonomy_manager = AutonomyManager(self.state_manager, self.map_registry)
        self.action_manager = ActionManager(self.state_manager, self.ros_runtime, self.autonomy_manager)
        self.manual_control_manager = ManualControlManager(self.state_manager, self.ros_runtime, self.watchdog)
        self.health_monitor = HealthMonitor(self.state_manager, self.ros_runtime)
        self.status_gateway = StatusGateway(self.state_manager)

    def refresh_health(self):
        self.health_monitor.refresh()

    def get_status(self):
        return self.status_gateway.get_status()

    def note_session_seen(self, session_id: str, timestamp_sec: float = None):
        self.watchdog.note_session_seen(session_id, timestamp_sec or time.time())

    def select_mode(self, mode_name: str):
        return self.mode_manager.select_mode(ControlMode(mode_name))

    def dispatch_action(self, action_name: str):
        action = ActionType(action_name)
        if action == ActionType.START:
            return self.action_manager.start()
        if action == ActionType.ESTOP:
            return self.action_manager.estop()
        if action == ActionType.SAFE_STOP:
            return self.action_manager.safe_stop()
        raise ValueError("Unsupported action: %s" % action_name)

    def submit_manual_intent(self, forward_axis: float, turn_axis: float, session_id: str, timestamp_sec: float = None):
        if timestamp_sec is None:
            timestamp_sec = time.time()
        intent = ManualIntent(
            forward_axis=forward_axis,
            turn_axis=turn_axis,
            timestamp_sec=timestamp_sec,
            session_id=session_id,
        )
        return self.manual_control_manager.submit_intent(intent)

    def set_speed_level(self, speed_level: int) -> ActionResult:
        max_index = max(len(list(self.config.manual_control.speed_levels_mps)) - 1, 0)
        normalized = max(0, min(int(speed_level), max_index))
        self.state_manager.set_speed_level(normalized)
        result = ActionResult(
            ActionType.SET_SPEED_LEVEL,
            True,
            "speed_level_updated",
            "speed level updated",
            {"speed_level": str(normalized)},
        )
        self.state_manager.set_last_action(result)
        return result

    def list_maps(self):
        return self.map_registry.list_maps()

    def save_map(self, display_name: str) -> ActionResult:
        result = self.map_registry.save_map(display_name, self.state_manager.snapshot().selected_mode)
        self.state_manager.set_last_action(result)
        return result

    def select_map(self, map_id: str) -> ActionResult:
        result = self.map_registry.select_map(map_id)
        self.state_manager.set_last_action(result)
        return result

    def rename_map(self, map_id: str, display_name: str) -> ActionResult:
        result = self.map_registry.rename_map(map_id, display_name)
        self.state_manager.set_last_action(result)
        return result

    def get_map_preview_info(self, requested_map_id: str = ""):
        status = self.state_manager.snapshot()
        return self.map_registry.get_preview_info(
            current_mode=status.selected_mode,
            selected_map_id=status.selected_map.map_id,
            requested_map_id=requested_map_id,
        )

    def process_timeouts(self):
        if self.watchdog.session_expired():
            self.state_manager.set_ui_connected(False)
        self.manual_control_manager.handle_timeout()
