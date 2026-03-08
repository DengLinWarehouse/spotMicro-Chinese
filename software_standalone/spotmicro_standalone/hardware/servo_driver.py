from __future__ import annotations

import logging
import math
from typing import Dict

from ..config.loader import ServoParameters, StandaloneConfig
from .board import ServoBoard

LOG = logging.getLogger(__name__)


class ServoDriver:
    """Convert leg joint angles to PWM commands."""

    def __init__(self, config: StandaloneConfig, board: ServoBoard) -> None:
        self._config = config
        self._board = board

    def _angle_to_pwm(self, servo: ServoParameters, angle_rad: float) -> int:
        center_angle_rad = math.radians(servo.center_angle_deg)
        max_angle_rad = math.radians(self._config.servo_max_angle_deg)

        proportional = (angle_rad - center_angle_rad) / max_angle_rad
        proportional = max(min(proportional, 1.0), -1.0)

        offset = servo.direction * ((servo.range / 2.0) * proportional)
        pwm = int(round(servo.center + offset))
        return max(0, min(4095, pwm))

    def send_joint_angles(self, joint_angles: Dict[str, float]) -> None:
        """Send servo commands given a dict of joint angles in radians."""
        pwm_commands: Dict[int, int] = {}
        for name, servo in self._config.servos.items():
            if name not in joint_angles:
                continue
            pwm_commands[servo.num] = self._angle_to_pwm(servo, joint_angles[name])

        if not pwm_commands:
            LOG.warning("No servo commands computed; skipping board update")
            return
        self._board.send_absolute(pwm_commands)

    def stop(self) -> None:
        self._board.stop()
