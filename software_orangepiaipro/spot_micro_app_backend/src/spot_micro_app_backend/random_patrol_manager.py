from __future__ import annotations

import random
import time
from threading import RLock
from typing import Optional

from .models import ControlMode, ControlSource, RuntimeState
from .ros_runtime_adapter import PatrolConfig, RosRuntimeAdapter
from .state_manager import StateManager


class RandomPatrolManager(object):
    def __init__(self, state_manager: StateManager, ros_runtime: RosRuntimeAdapter, config: PatrolConfig):
        self._state_manager = state_manager
        self._ros_runtime = ros_runtime
        self._config = config
        self._rng = random.Random()
        self._lock = RLock()
        self._segment_name = ""
        self._segment_linear_x = 0.0
        self._segment_angular_z = 0.0
        self._segment_end_at = 0.0
        self._pending_segment = None
        self._transition_until = 0.0
        self._sent_zero_after_exit = False

    def tick(self, now: Optional[float] = None):
        now = time.time() if now is None else float(now)
        state = self._state_manager.snapshot()
        if not self._is_patrol_active(state):
            self._stop_output(now, state.selected_mode)
            return

        with self._lock:
            self._sent_zero_after_exit = False
            if self._transition_until > now:
                self._publish_zero(state.selected_mode)
                return

            if self._pending_segment is not None:
                self._activate_pending_segment_locked(now)

            if self._segment_end_at <= now:
                self._queue_next_segment_locked(now)
                self._publish_zero(state.selected_mode)
                return

            self._ros_runtime.publish_auto_command(
                self._segment_linear_x,
                self._segment_angular_z,
                state.selected_mode,
            )

    def _is_patrol_active(self, state) -> bool:
        return (
            state.selected_mode == ControlMode.AUTO_PATROL
            and state.runtime_state == RuntimeState.RUNNING_AUTO_PATROL
            and state.armed
            and state.current_control_source == ControlSource.AUTO
            and not state.estop_latched
            and not state.fault_active
        )

    def _stop_output(self, now: float, mode: ControlMode):
        with self._lock:
            active = bool(self._segment_name or self._pending_segment is not None or self._transition_until > 0.0)
            self._segment_name = ""
            self._segment_linear_x = 0.0
            self._segment_angular_z = 0.0
            self._segment_end_at = 0.0
            self._pending_segment = None
            self._transition_until = 0.0
            if active or not self._sent_zero_after_exit:
                self._publish_zero(mode)
                self._sent_zero_after_exit = True

    def _queue_next_segment_locked(self, now: float):
        segment_name, linear_x, angular_z, duration_sec = self._build_random_segment_locked()
        self._pending_segment = {
            "name": segment_name,
            "linear_x": linear_x,
            "angular_z": angular_z,
            "duration_sec": duration_sec,
        }
        self._transition_until = now + max(float(self._config.zero_transition_sec), 0.0)

    def _activate_pending_segment_locked(self, now: float):
        if self._pending_segment is None:
            return
        segment = self._pending_segment
        self._pending_segment = None
        self._transition_until = 0.0
        self._segment_name = str(segment["name"])
        self._segment_linear_x = float(segment["linear_x"])
        self._segment_angular_z = float(segment["angular_z"])
        self._segment_end_at = now + float(segment["duration_sec"])

    def _build_random_segment_locked(self):
        roll = self._rng.random()
        forward_threshold = min(max(float(self._config.forward_probability), 0.0), 1.0)
        pause_threshold = min(max(float(self._config.pause_probability), 0.0), 1.0)

        if roll < pause_threshold:
            return (
                "pause",
                0.0,
                0.0,
                self._sample_duration(self._config.pause_segment_sec_min, self._config.pause_segment_sec_max),
            )
        if roll < pause_threshold + forward_threshold:
            return (
                "cruise",
                max(float(self._config.forward_speed_mps), 0.0),
                0.0,
                self._sample_duration(self._config.cruise_segment_sec_min, self._config.cruise_segment_sec_max),
            )

        turn_direction = -1.0 if self._rng.random() < 0.5 else 1.0
        return (
            "turn",
            0.0,
            turn_direction * abs(float(self._config.turn_rate_rad_s)),
            self._sample_duration(self._config.turn_segment_sec_min, self._config.turn_segment_sec_max),
        )

    def _sample_duration(self, lower: float, upper: float) -> float:
        lower = float(lower)
        upper = float(upper)
        if upper < lower:
            lower, upper = upper, lower
        if upper <= lower:
            return max(lower, 0.0)
        return self._rng.uniform(max(lower, 0.0), max(upper, 0.0))

    def _publish_zero(self, mode: ControlMode):
        self._ros_runtime.publish_auto_command(0.0, 0.0, mode)
