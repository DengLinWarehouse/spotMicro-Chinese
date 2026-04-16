from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class RuntimeState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    READY_DISARMED = "READY_DISARMED"
    STARTING = "STARTING"
    ARMED_READY = "ARMED_READY"
    RUNNING_MANUAL = "RUNNING_MANUAL"
    RUNNING_MANUAL_MAPPING = "RUNNING_MANUAL_MAPPING"
    RUNNING_AUTO_EXPLORE = "RUNNING_AUTO_EXPLORE"
    RUNNING_AUTO_PATROL = "RUNNING_AUTO_PATROL"
    SAFE_STOPPING = "SAFE_STOPPING"
    ESTOP_LATCHED = "ESTOP_LATCHED"
    FAULT = "FAULT"


class ControlMode(str, Enum):
    MANUAL = "MANUAL"
    MANUAL_MAPPING = "MANUAL_MAPPING"
    AUTO_EXPLORE_MAPPING = "AUTO_EXPLORE_MAPPING"
    AUTO_PATROL = "AUTO_PATROL"


class ActionType(str, Enum):
    START = "START"
    ESTOP = "ESTOP"
    SAFE_STOP = "SAFE_STOP"
    RESET_FAULT = "RESET_FAULT"
    SAVE_MAP = "SAVE_MAP"
    MANUAL_INTENT = "MANUAL_INTENT"
    SELECT_MODE = "SELECT_MODE"
    SET_SPEED_LEVEL = "SET_SPEED_LEVEL"
    SET_SPEED_LEVEL = "SET_SPEED_LEVEL"


class ControlSource(str, Enum):
    NONE = "none"
    MANUAL = "manual"
    AUTO = "auto"
    ESTOP = "estop"


@dataclass(frozen=True)
class ManualIntent:
    forward_axis: float
    turn_axis: float
    timestamp_sec: float
    session_id: str

    def is_neutral(self, deadband: float = 1e-3) -> bool:
        return abs(self.forward_axis) <= deadband and abs(self.turn_axis) <= deadband


@dataclass(frozen=True)
class ActionResult:
    action: ActionType
    accepted: bool
    code: str
    message: str
    details: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "action": self.action.value,
            "accepted": self.accepted,
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class RuntimeHealth:
    connected: bool
    mode: str
    message: str = ""


@dataclass
class MapSelection:
    map_id: str = ""
    display_name: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "map_id": self.map_id,
            "display_name": self.display_name,
        }


@dataclass
class BackendState:
    runtime_state: RuntimeState = RuntimeState.READY_DISARMED
    selected_mode: ControlMode = ControlMode.MANUAL
    armed: bool = False
    estop_latched: bool = False
    fault_active: bool = False
    fault_reason: str = ""
    selected_map: MapSelection = field(default_factory=MapSelection)
    speed_level: int = 0
    current_control_source: ControlSource = ControlSource.NONE
    ros_connected: bool = False
    ui_connected: bool = False
    last_manual_input_at: float = 0.0
    last_session_seen_at: float = 0.0
    last_session_id: str = ""
    last_action: Optional[ActionResult] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "runtime_state": self.runtime_state.value,
            "selected_mode": self.selected_mode.value,
            "armed": self.armed,
            "estop_latched": self.estop_latched,
            "fault_active": self.fault_active,
            "fault_reason": self.fault_reason,
            "selected_map": self.selected_map.to_dict(),
            "speed_level": self.speed_level,
            "current_control_source": self.current_control_source.value,
            "ros_connected": self.ros_connected,
            "ui_connected": self.ui_connected,
            "last_manual_input_at": self.last_manual_input_at,
            "last_session_seen_at": self.last_session_seen_at,
            "last_session_id": self.last_session_id,
            "last_action": self.last_action.to_dict() if self.last_action else None,
        }
