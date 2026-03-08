from __future__ import annotations

import math
import os
import sys
import threading
import time
from dataclasses import dataclass, replace
from typing import Optional

from ..config.loader import ControlLimits, StandaloneConfig, TeleopConfig


@dataclass
class KeyboardCommandState:
    x_speed: float = 0.0
    y_speed: float = 0.0
    yaw_rate: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    height: float = -0.15
    trot_event: bool = False
    activate_event: bool = False
    shutdown: bool = False


class _KeyReader:
    """Cross-platform non-blocking key reader."""

    def __enter__(self):
        if os.name != "nt":
            import termios
            import tty

            self._fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        return self

    def __exit__(self, exc_type, exc, tb):
        if os.name != "nt":
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)

    def read_key(self, timeout: float = 0.05) -> Optional[str]:
        if os.name == "nt":
            import msvcrt

            end = time.time() + timeout
            while time.time() < end:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):
                        # Special key prefix, drop next char
                        if msvcrt.kbhit():
                            msvcrt.getwch()
                        continue
                    return ch
                time.sleep(0.005)
            return None

        import select

        readable, _, _ = select.select([sys.stdin], [], [], timeout)
        if readable:
            ch = sys.stdin.read(1)
            if ch == "\x03":  # Ctrl-C
                raise KeyboardInterrupt
            return ch
        return None


class KeyboardInput(threading.Thread):
    """Background thread that captures keyboard commands."""

    def __init__(self, config: StandaloneConfig):
        super().__init__(daemon=True)
        self._teleop = config.teleop
        self._control = config.control
        self._stance = config.stance
        height = -config.stance.default_stand_height
        self._state = KeyboardCommandState(height=height)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._min_height = -config.stance.default_stand_height - 0.02
        self._max_height = -config.stance.lie_down_height + 0.01
        if self._min_height > self._max_height:
            self._min_height, self._max_height = self._max_height, self._min_height
        self._angle_limit = math.radians(18.0)

    def snapshot(self) -> KeyboardCommandState:
        with self._lock:
            snap = replace(self._state)
            self._state.trot_event = False
            self._state.activate_event = False
            return snap

    def request_stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        self._print_help()
        reader = _KeyReader()
        with reader:
            while not self._stop.is_set():
                key = reader.read_key(timeout=0.05)
                if key:
                    if key == "\x1b":  # ESC
                        with self._lock:
                            self._state.shutdown = True
                        self._stop.set()
                        break
                    self._handle_key(key.lower())

    def _print_help(self) -> None:
        instructions = """
Spot Micro Standalone Teleop
----------------------------
 w/s : forward/backward velocity
 a/d : left/right velocity
 q/e : yaw rate
 r/f : raise/lower body
 t/g : pitch forward/backward
 y/h : roll left/right
 space : toggle trot mode
 enter : activate (stand) from idle
 c : zero all motion commands
 esc : exit program
"""
        print(instructions.strip())

    def _handle_key(self, key: str) -> None:
        with self._lock:
            if key == "w":
                self._state.x_speed = self._clamp(
                    self._state.x_speed + self._teleop.speed_increment,
                    -self._control.max_fwd_velocity,
                    self._control.max_fwd_velocity,
                )
            elif key == "s":
                self._state.x_speed = self._clamp(
                    self._state.x_speed - self._teleop.speed_increment,
                    -self._control.max_fwd_velocity,
                    self._control.max_fwd_velocity,
                )
            elif key == "a":
                self._state.y_speed = self._clamp(
                    self._state.y_speed + self._teleop.lateral_increment,
                    -self._control.max_side_velocity,
                    self._control.max_side_velocity,
                )
            elif key == "d":
                self._state.y_speed = self._clamp(
                    self._state.y_speed - self._teleop.lateral_increment,
                    -self._control.max_side_velocity,
                    self._control.max_side_velocity,
                )
            elif key == "q":
                self._state.yaw_rate = self._clamp(
                    self._state.yaw_rate + self._teleop.yaw_rate_increment,
                    -self._control.max_yaw_rate,
                    self._control.max_yaw_rate,
                )
            elif key == "e":
                self._state.yaw_rate = self._clamp(
                    self._state.yaw_rate - self._teleop.yaw_rate_increment,
                    -self._control.max_yaw_rate,
                    self._control.max_yaw_rate,
                )
            elif key == "r":
                self._state.height = self._clamp(
                    self._state.height + self._teleop.height_increment,
                    self._min_height,
                    self._max_height,
                )
            elif key == "f":
                self._state.height = self._clamp(
                    self._state.height - self._teleop.height_increment,
                    self._min_height,
                    self._max_height,
                )
            elif key == "t":
                self._state.pitch = self._clamp(
                    self._state.pitch - self._teleop.pitch_increment,
                    -self._angle_limit,
                    self._angle_limit,
                )
            elif key == "g":
                self._state.pitch = self._clamp(
                    self._state.pitch + self._teleop.pitch_increment,
                    -self._angle_limit,
                    self._angle_limit,
                )
            elif key == "y":
                self._state.roll = self._clamp(
                    self._state.roll - self._teleop.roll_increment,
                    -self._angle_limit,
                    self._angle_limit,
                )
            elif key == "h":
                self._state.roll = self._clamp(
                    self._state.roll + self._teleop.roll_increment,
                    -self._angle_limit,
                    self._angle_limit,
                )
            elif key == " ":
                self._state.trot_event = True
            elif key in ("\r", "\n"):
                self._state.activate_event = True
            elif key == "c":
                self._state.x_speed = 0.0
                self._state.y_speed = 0.0
                self._state.yaw_rate = 0.0
                self._state.roll = 0.0
                self._state.pitch = 0.0
            # ignore other keys

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))
