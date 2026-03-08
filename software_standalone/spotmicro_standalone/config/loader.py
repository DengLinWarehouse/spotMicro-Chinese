from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import yaml


@dataclass(frozen=True)
class RobotGeometry:
    hip_link_length: float
    upper_leg_link_length: float
    lower_leg_link_length: float
    body_width: float
    body_length: float


@dataclass(frozen=True)
class StanceConfig:
    default_stand_height: float
    stand_front_x_offset: float
    stand_back_x_offset: float
    lie_down_height: float
    lie_down_foot_x_offset: float


@dataclass(frozen=True)
class ServoParameters:
    name: str
    num: int
    center: int
    range: int
    direction: int
    center_angle_deg: float


@dataclass(frozen=True)
class ControlLimits:
    dt: float
    max_fwd_velocity: float
    max_side_velocity: float
    max_yaw_rate: float


@dataclass(frozen=True)
class GaitParameters:
    z_clearance: float
    alpha: float
    beta: float
    num_phases: int
    rb_contact_phases: List[int]
    rf_contact_phases: List[int]
    lf_contact_phases: List[int]
    lb_contact_phases: List[int]
    overlap_time: float
    swing_time: float
    foot_height_time_constant: float
    body_shift_phases: List[int]
    fwd_body_balance_shift: float
    back_body_balance_shift: float
    side_body_balance_shift: float


@dataclass(frozen=True)
class TeleopConfig:
    speed_increment: float = 0.02
    lateral_increment: float = 0.02
    yaw_rate_increment_deg: float = 2.0
    angle_increment_deg: float = 2.5
    height_increment: float = 0.01
    roll_increment_deg: float = 2.0
    pitch_increment_deg: float = 2.0

    @property
    def yaw_rate_increment(self) -> float:
        return np.deg2rad(self.yaw_rate_increment_deg)

    @property
    def angle_increment(self) -> float:
        return np.deg2rad(self.angle_increment_deg)

    @property
    def roll_increment(self) -> float:
        return np.deg2rad(self.roll_increment_deg)

    @property
    def pitch_increment(self) -> float:
        return np.deg2rad(self.pitch_increment_deg)


@dataclass(frozen=True)
class HardwareConfig:
    backend: str = "mock"
    i2c_bus: int = 1
    i2c_address: int = 0x40
    pwm_frequency: int = 50


@dataclass(frozen=True)
class StandaloneConfig:
    geometry: RobotGeometry
    stance: StanceConfig
    servo_max_angle_deg: float
    servos: Dict[str, ServoParameters]
    control: ControlLimits
    gait: GaitParameters
    teleop: TeleopConfig = field(default_factory=TeleopConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)

    @classmethod
    def from_dict(cls, data: Dict) -> "StandaloneConfig":
        robot = RobotGeometry(**data["robot"])
        stance = StanceConfig(**data["stance"])

        servo_section = data["servo"]
        servo_max_angle = float(servo_section["servo_max_angle_deg"])
        servos = {
            name: ServoParameters(name=name, **params)
            for name, params in servo_section["layout"].items()
        }

        control = ControlLimits(**data["control"])
        gait = GaitParameters(**data["gait"])
        teleop = TeleopConfig(**data.get("teleop", {}))
        hardware = HardwareConfig(**data.get("hardware", {}))

        return cls(
            geometry=robot,
            stance=stance,
            servo_max_angle_deg=servo_max_angle,
            servos=servos,
            control=control,
            gait=gait,
            teleop=teleop,
            hardware=hardware,
        )

    def contact_matrix(self) -> np.ndarray:
        """Return gait contact schedule in the order RF, LF, RB, LB."""
        return np.array(
            [
                self.gait.rf_contact_phases,
                self.gait.lf_contact_phases,
                self.gait.rb_contact_phases,
                self.gait.lb_contact_phases,
            ],
            dtype=float,
        )

    def servo_order(self) -> List[ServoParameters]:
        """Return servos sorted by physical channel index."""
        return sorted(self.servos.values(), key=lambda s: s.num)


def load_config(path: Optional[str | Path] = None) -> StandaloneConfig:
    """Load the standalone config from disk."""
    if path is None:
        path = Path(__file__).with_name("default.yaml")
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config file {path} does not exist")

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    return StandaloneConfig.from_dict(data)
