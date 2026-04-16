from __future__ import annotations

import time

from .action_manager import ActionManager
from .health_monitor import HealthMonitor
from .manual_control_manager import ManualControlManager
from .map_registry import MapRegistry
from .mode_manager import ModeManager
from .models import ActionResult, ActionType, ControlMode, ManualIntent
from .ros_runtime_adapter import DryRunRosRuntimeAdapter, RuntimeAdapterConfig, TopicRosRuntimeAdapter
from .session_watchdog import SessionWatchdog
from .state_manager import StateManager
from .status_gateway import StatusGateway


class SpotMicroAppBackend(object):
    def __init__(self, config: RuntimeAdapterConfig):
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
        self.action_manager = ActionManager(self.state_manager, self.ros_runtime)
        self.manual_control_manager = ManualControlManager(self.state_manager, self.ros_runtime, self.watchdog)
        self.health_monitor = HealthMonitor(self.state_manager, self.ros_runtime)
        self.map_registry = MapRegistry(self.state_manager)
        self.status_gateway = StatusGateway(self.state_manager)
        self.state_manager.set_selected_map("", "")

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

    def process_timeouts(self):
        if self.watchdog.session_expired():
            self.state_manager.set_ui_connected(False)
        self.manual_control_manager.handle_timeout()
