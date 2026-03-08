from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from ..config import StandaloneConfig, load_config
from ..hardware import ServoDriver, create_board
from ..interfaces import KeyboardInput
from ..pupper.Config import Configuration as PupperConfiguration
from ..pupper_src.Command import Command
from ..pupper_src.Controller import Controller
from ..pupper_src.State import State
from ..spot_micro_kinematics.spot_micro_stick_figure import SpotMicroStickFigure

LOG = logging.getLogger(__name__)


class SpotMicroTeleop:
    """High-level runtime that mirrors the ROS pipeline without ROS."""

    def __init__(
        self,
        config_path: Optional[str | Path] = None,
        *,
        backend: Optional[str] = None,
        pwm_frequency: Optional[int] = None,
        i2c_bus: Optional[int] = None,
        i2c_address: Optional[int] = None,
    ) -> None:
        self._cfg = load_config(config_path)

        backend = backend or self._cfg.hardware.backend
        pwm_frequency = pwm_frequency or self._cfg.hardware.pwm_frequency
        i2c_bus = i2c_bus or self._cfg.hardware.i2c_bus
        i2c_address = i2c_address or self._cfg.hardware.i2c_address

        self._board = create_board(
            backend, bus=i2c_bus, address=i2c_address, pwm_frequency=pwm_frequency
        )
        self._driver = ServoDriver(self._cfg, self._board)
        self._keyboard = KeyboardInput(self._cfg)

        self._pupper_cfg = self._build_pupper_config()
        self._controller = Controller(self._pupper_cfg)
        self._state = State()
        self._command = Command()
        self._stick = SpotMicroStickFigure(y=self._cfg.stance.default_stand_height)
        self._default_height = self._cfg.stance.default_stand_height
        self._init_state()

    def _build_pupper_config(self) -> PupperConfiguration:
        cfg = self._cfg
        pcfg = PupperConfiguration()
        pcfg.max_x_velocity = cfg.control.max_fwd_velocity
        pcfg.max_y_velocity = cfg.control.max_side_velocity
        pcfg.max_yaw_rate = cfg.control.max_yaw_rate
        pcfg.delta_x = cfg.geometry.body_length / 2.0
        pcfg.delta_y = cfg.geometry.body_width / 2.0 + cfg.geometry.hip_link_length
        pcfg.x_shift_front = cfg.stance.stand_front_x_offset
        pcfg.x_shift_back = cfg.stance.stand_back_x_offset
        pcfg.default_z_ref = -cfg.stance.default_stand_height
        pcfg.z_clearance = cfg.gait.z_clearance
        pcfg.alpha = cfg.gait.alpha
        pcfg.beta = cfg.gait.beta
        pcfg.dt = cfg.control.dt
        pcfg.num_phases = cfg.gait.num_phases
        pcfg.contact_phases = cfg.contact_matrix()
        pcfg.overlap_time = cfg.gait.overlap_time
        pcfg.swing_time = cfg.gait.swing_time
        pcfg.body_shift_x = cfg.gait.fwd_body_balance_shift
        pcfg.body_shift_y = cfg.gait.side_body_balance_shift
        pcfg.z_time_constant = cfg.gait.foot_height_time_constant
        return pcfg

    def _init_state(self) -> None:
        cfg = self._cfg
        l = cfg.geometry.body_length
        w = cfg.geometry.body_width
        l1 = cfg.geometry.hip_link_length

        default_feet = np.array(
            [
                [-l / 2, 0, w / 2 + l1],
                [l / 2, 0, w / 2 + l1],
                [l / 2, 0, -(w / 2 + l1)],
                [-l / 2, 0, -(w / 2 + l1)],
            ]
        )
        self._stick.set_absolute_foot_coordinates(default_feet)
        self._state.foot_locations = (
            self._pupper_cfg.default_stance
            + np.array([0, 0, -self._default_height])[:, np.newaxis]
        )
        self._command.height = -self._default_height

    def _convert_foot_positions(self, controller_positions: np.ndarray) -> np.ndarray:
        """Convert pupper ordering to Spot Micro ordering."""
        return np.array(
            [
                [
                    controller_positions[0, 2],
                    self._default_height + controller_positions[2, 2],
                    -controller_positions[1, 2],
                ],
                [
                    controller_positions[0, 0],
                    self._default_height + controller_positions[2, 0],
                    -controller_positions[1, 0],
                ],
                [
                    controller_positions[0, 1],
                    self._default_height + controller_positions[2, 1],
                    -controller_positions[1, 1],
                ],
                [
                    controller_positions[0, 3],
                    self._default_height + controller_positions[2, 3],
                    -controller_positions[1, 3],
                ],
            ]
        )

    def _leg_angles_to_map(self, leg_angles: np.ndarray) -> Dict[str, float]:
        return {
            "RB_1": leg_angles[0][0],
            "RB_2": leg_angles[0][1],
            "RB_3": leg_angles[0][2],
            "RF_1": leg_angles[1][0],
            "RF_2": leg_angles[1][1],
            "RF_3": leg_angles[1][2],
            "LF_1": leg_angles[2][0],
            "LF_2": leg_angles[2][1],
            "LF_3": leg_angles[2][2],
            "LB_1": leg_angles[3][0],
            "LB_2": leg_angles[3][1],
            "LB_3": leg_angles[3][2],
        }

    def _apply_keyboard_state(self) -> bool:
        snapshot = self._keyboard.snapshot()
        if snapshot.shutdown:
            return False

        self._command.horizontal_velocity = np.array([snapshot.x_speed, snapshot.y_speed])
        self._command.yaw_rate = snapshot.yaw_rate
        self._command.roll = snapshot.roll
        self._command.pitch = snapshot.pitch
        self._command.height = snapshot.height
        self._command.trot_event = snapshot.trot_event
        self._command.activate_event = snapshot.activate_event
        return True

    def run(self) -> None:
        """Main control loop."""
        LOG.info("Starting Spot Micro standalone teleop")
        self._keyboard.start()
        loop_dt = self._cfg.control.dt
        try:
            while True:
                if not self._apply_keyboard_state():
                    break
                foot_positions = self._controller.run(self._state, self._command)
                sm_positions = self._convert_foot_positions(foot_positions)
                self._stick.set_absolute_foot_coordinates(sm_positions)
                leg_angles = self._stick.get_leg_angles()
                self._driver.send_joint_angles(self._leg_angles_to_map(leg_angles))
                time.sleep(loop_dt)
        except KeyboardInterrupt:
            LOG.info("Keyboard interrupt received, shutting down")
        finally:
            self._keyboard.request_stop()
            self._keyboard.join(timeout=1.0)
            self._driver.stop()
