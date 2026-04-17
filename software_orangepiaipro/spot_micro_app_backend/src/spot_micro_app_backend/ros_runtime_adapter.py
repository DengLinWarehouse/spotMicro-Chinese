from __future__ import annotations

from dataclasses import dataclass
import time

import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String

from .models import ActionResult, ActionType, ControlMode, ManualIntent, RuntimeHealth


@dataclass(frozen=True)
class RuntimeAdapterTopics:
    stand_topic: str = "/stand_cmd"
    walk_topic: str = "/walk_cmd"
    idle_topic: str = "/idle_cmd"
    enable_topic: str = "/spot_micro/auto_mode/enable"
    stop_topic: str = "/spot_micro/auto_explore/stop"
    manual_cmd_topic: str = "/cmd_vel_manual"
    auto_cmd_topic: str = "/cmd_vel_auto"
    cmd_vel_topic: str = "/cmd_vel"
    cmd_vel_source_topic: str = "/spot_micro/cmd_vel_arbiter/source"
    map_topic: str = "/map"


@dataclass(frozen=True)
class LifecycleConfig:
    startup_idle_enabled: bool = True
    startup_idle_delay_sec: float = 0.30
    startup_stand_delay_sec: float = 1.80
    startup_walk_delay_sec: float = 1.60
    startup_auto_enable_delay_sec: float = 0.80
    startup_zero_cmd_duration_sec: float = 0.80
    shutdown_zero_cmd_duration_sec: float = 1.00
    shutdown_stand_hold_sec: float = 1.20
    pulse_count: int = 3
    pulse_interval_sec: float = 0.20
    estop_zero_cmd_duration_sec: float = 0.40


@dataclass(frozen=True)
class ManualControlConfig:
    speed_levels_mps: list
    turn_rate_max_rad_s: float = 0.18
    direction_deadband: float = 0.15
    turn_deadband: float = 0.12
    forward_smoothing_tau_sec: float = 0.18
    turn_smoothing_tau_sec: float = 0.28
    linear_accel_limit_mps2: float = 0.22
    angular_accel_limit_rad_s2: float = 0.80
    direct_cmd_vel_bridge_enabled: bool = True
    direct_cmd_vel_bridge_modes: tuple = ("MANUAL", "MANUAL_MAPPING")


@dataclass(frozen=True)
class PatrolConfig:
    forward_speed_mps: float = 0.08
    turn_rate_rad_s: float = 0.45
    cruise_segment_sec_min: float = 1.8
    cruise_segment_sec_max: float = 3.6
    turn_segment_sec_min: float = 0.7
    turn_segment_sec_max: float = 1.5
    pause_segment_sec_min: float = 0.4
    pause_segment_sec_max: float = 1.0
    forward_probability: float = 0.58
    pause_probability: float = 0.12
    zero_transition_sec: float = 0.12
    live_execution_enabled: bool = False


@dataclass(frozen=True)
class RuntimeAdapterConfig:
    dry_run: bool = True
    health_poll_hz: float = 2.0
    manual_input_timeout_sec: float = 0.6
    session_timeout_sec: float = 2.0
    topics: RuntimeAdapterTopics = RuntimeAdapterTopics()
    lifecycle: LifecycleConfig = LifecycleConfig()
    manual_control: ManualControlConfig = ManualControlConfig(speed_levels_mps=(0.0, 0.03, 0.06, 0.09, 0.12))
    patrol: PatrolConfig = PatrolConfig()


class RosRuntimeAdapter(object):
    def probe_health(self) -> RuntimeHealth:
        raise NotImplementedError

    def request_start(self, mode: ControlMode) -> ActionResult:
        raise NotImplementedError

    def request_estop(self) -> ActionResult:
        raise NotImplementedError

    def request_safe_stop(self) -> ActionResult:
        raise NotImplementedError

    def publish_manual_intent(self, intent: ManualIntent, speed_level: int, mode: ControlMode) -> ActionResult:
        raise NotImplementedError

    def publish_auto_command(self, linear_x: float, angular_z: float, mode: ControlMode) -> ActionResult:
        raise NotImplementedError


class DryRunRosRuntimeAdapter(RosRuntimeAdapter):
    def __init__(self, config: RuntimeAdapterConfig):
        self._config = config

    def probe_health(self) -> RuntimeHealth:
        if self._config.dry_run:
            return RuntimeHealth(connected=True, mode="dry_run", message="using backend skeleton dry-run adapter")
        return RuntimeHealth(connected=False, mode="offline", message="live ROS adapter not implemented yet")

    def request_start(self, mode: ControlMode) -> ActionResult:
        if self._config.dry_run:
            return ActionResult(
                ActionType.START, True, "dry_run_ok", "start accepted in dry-run mode", {"mode": mode.value}
            )
        return ActionResult(ActionType.START, False, "not_implemented", "live ROS start path is not implemented yet")

    def request_estop(self) -> ActionResult:
        if self._config.dry_run:
            return ActionResult(ActionType.ESTOP, True, "dry_run_ok", "estop accepted in dry-run mode")
        return ActionResult(ActionType.ESTOP, False, "not_implemented", "live ROS estop path is not implemented yet")

    def request_safe_stop(self) -> ActionResult:
        if self._config.dry_run:
            return ActionResult(ActionType.SAFE_STOP, True, "dry_run_ok", "safe stop accepted in dry-run mode")
        return ActionResult(
            ActionType.SAFE_STOP, False, "not_implemented", "live ROS safe-stop path is not implemented yet"
        )

    def publish_manual_intent(self, intent: ManualIntent, speed_level: int, mode: ControlMode) -> ActionResult:
        if self._config.dry_run:
            details = {
                "forward_axis": str(intent.forward_axis),
                "turn_axis": str(intent.turn_axis),
                "speed_level": str(speed_level),
                "mode": mode.value,
            }
            return ActionResult(
                ActionType.MANUAL_INTENT, True, "dry_run_ok", "manual intent accepted in dry-run mode", details=details
            )
        return ActionResult(
            ActionType.MANUAL_INTENT, False, "not_implemented", "live ROS manual intent path is not implemented yet"
        )

    def publish_auto_command(self, linear_x: float, angular_z: float, mode: ControlMode) -> ActionResult:
        if self._config.dry_run:
            return ActionResult(
                ActionType.MANUAL_INTENT,
                True,
                "dry_run_ok",
                "auto command accepted in dry-run mode",
                details={
                    "linear_x": "%.3f" % float(linear_x),
                    "angular_z": "%.3f" % float(angular_z),
                    "mode": mode.value,
                    "bridged_to_cmd_vel": "false",
                },
            )
        return ActionResult(
            ActionType.MANUAL_INTENT, False, "not_implemented", "live ROS auto command path is not implemented yet"
        )


class TopicRosRuntimeAdapter(RosRuntimeAdapter):
    def __init__(self, config: RuntimeAdapterConfig):
        self._config = config
        self._topics = config.topics
        self._lifecycle = config.lifecycle
        self._manual_control = config.manual_control
        self._last_cmd_vel_source = ""
        self._last_cmd_vel_source_at = 0.0
        self._stand_pub = rospy.Publisher(self._topics.stand_topic, Bool, queue_size=1, latch=True)
        self._walk_pub = rospy.Publisher(self._topics.walk_topic, Bool, queue_size=1, latch=True)
        self._idle_pub = rospy.Publisher(self._topics.idle_topic, Bool, queue_size=1, latch=True)
        self._enable_pub = rospy.Publisher(self._topics.enable_topic, Bool, queue_size=1, latch=True)
        self._stop_pub = rospy.Publisher(self._topics.stop_topic, Bool, queue_size=1, latch=True)
        self._manual_pub = rospy.Publisher(self._topics.manual_cmd_topic, Twist, queue_size=1)
        self._auto_pub = rospy.Publisher(self._topics.auto_cmd_topic, Twist, queue_size=1)
        self._cmd_vel_pub = rospy.Publisher(self._topics.cmd_vel_topic, Twist, queue_size=1)
        self._source_sub = rospy.Subscriber(
            self._topics.cmd_vel_source_topic, String, self._source_cb, queue_size=1
        )
        self._last_manual_twist = Twist()
        self._last_manual_publish_at = time.time()

    def _source_cb(self, msg: String):
        self._last_cmd_vel_source = msg.data
        self._last_cmd_vel_source_at = time.time()

    def _reset_manual_command_filter(self):
        self._last_manual_twist = Twist()
        self._last_manual_publish_at = time.time()

    @staticmethod
    def _apply_deadband_curve(value: float, deadband: float) -> float:
        magnitude = abs(float(value))
        deadband = max(float(deadband), 0.0)
        if magnitude <= deadband:
            return 0.0
        if deadband >= 0.999:
            return 0.0
        scaled = (magnitude - deadband) / (1.0 - deadband)
        return max(min(scaled, 1.0), 0.0) * (1.0 if value >= 0.0 else -1.0)

    @staticmethod
    def _clamp_rate(current: float, target: float, rate_limit: float, dt: float) -> float:
        if rate_limit <= 0.0 or dt <= 0.0:
            return target
        max_delta = rate_limit * dt
        delta = target - current
        if delta > max_delta:
            return current + max_delta
        if delta < -max_delta:
            return current - max_delta
        return target

    def _smooth_manual_value(self, current: float, target: float, tau: float, rate_limit: float, dt: float) -> float:
        if dt <= 0.0:
            return target
        tau = max(float(tau), 0.0)
        alpha = 1.0 if tau <= 1e-6 else max(min(dt / (tau + dt), 1.0), 0.0)
        filtered = current + alpha * (target - current)
        return self._clamp_rate(current, filtered, float(rate_limit), dt)

    def probe_health(self) -> RuntimeHealth:
        try:
            topics = dict(rospy.get_published_topics())
        except Exception as exc:
            return RuntimeHealth(connected=False, mode="offline", message="ros master unavailable: %s" % exc)

        required = [
            self._topics.manual_cmd_topic,
            self._topics.cmd_vel_topic,
            self._topics.enable_topic,
        ]
        missing = [topic for topic in required if topic not in topics]
        if missing:
            return RuntimeHealth(
                connected=True,
                mode="degraded",
                message="ros master reachable, missing topics: %s" % ", ".join(missing),
            )
        source_msg = self._last_cmd_vel_source or "no arbiter source observed yet"
        return RuntimeHealth(connected=True, mode="live", message=source_msg)

    def request_start(self, mode: ControlMode) -> ActionResult:
        self._reset_manual_command_filter()
        self._set_auto_enabled(False)
        self._request_stop(True)
        self._publish_zero_cmds(self._lifecycle.startup_zero_cmd_duration_sec)

        if self._lifecycle.startup_idle_enabled:
            if self._lifecycle.startup_idle_delay_sec > 0.0:
                rospy.sleep(self._lifecycle.startup_idle_delay_sec)
            self._pulse(self._idle_pub, self._lifecycle.pulse_count, self._lifecycle.pulse_interval_sec)

        if self._lifecycle.startup_stand_delay_sec > 0.0:
            rospy.sleep(self._lifecycle.startup_stand_delay_sec)
        self._pulse(self._stand_pub, self._lifecycle.pulse_count, self._lifecycle.pulse_interval_sec)

        if self._lifecycle.startup_walk_delay_sec > 0.0:
            rospy.sleep(self._lifecycle.startup_walk_delay_sec)
        self._pulse(self._walk_pub, self._lifecycle.pulse_count, self._lifecycle.pulse_interval_sec)

        auto_mode = mode in (ControlMode.AUTO_EXPLORE_MAPPING, ControlMode.AUTO_PATROL)
        if auto_mode:
            if self._lifecycle.startup_auto_enable_delay_sec > 0.0:
                rospy.sleep(self._lifecycle.startup_auto_enable_delay_sec)
            self._request_stop(False)
            self._set_auto_enabled(True)
        else:
            self._request_stop(True)
            self._set_auto_enabled(False)

        return ActionResult(ActionType.START, True, "ros_ok", "start sequence completed", {"mode": mode.value})

    def request_estop(self) -> ActionResult:
        self._reset_manual_command_filter()
        self._set_auto_enabled(False)
        self._request_stop(True)
        self._publish_zero_cmds(self._lifecycle.estop_zero_cmd_duration_sec)
        return ActionResult(ActionType.ESTOP, True, "ros_ok", "software estop sequence completed")

    def request_safe_stop(self) -> ActionResult:
        self._reset_manual_command_filter()
        self._set_auto_enabled(False)
        self._request_stop(True)
        self._publish_zero_cmds(self._lifecycle.shutdown_zero_cmd_duration_sec)
        self._pulse(self._stand_pub, self._lifecycle.pulse_count, self._lifecycle.pulse_interval_sec)
        if self._lifecycle.shutdown_stand_hold_sec > 0.0:
            rospy.sleep(self._lifecycle.shutdown_stand_hold_sec)
        self._pulse(self._idle_pub, self._lifecycle.pulse_count, self._lifecycle.pulse_interval_sec)
        self._publish_zero_cmds(0.20)
        return ActionResult(ActionType.SAFE_STOP, True, "ros_ok", "safe stop sequence completed")

    def publish_manual_intent(self, intent: ManualIntent, speed_level: int, mode: ControlMode) -> ActionResult:
        target = Twist()
        speed_levels = list(self._manual_control.speed_levels_mps)
        if not speed_levels:
            speed_levels = [0.0]
        speed_level = max(0, min(int(speed_level), len(speed_levels) - 1))
        selected_speed = float(speed_levels[speed_level])

        forward_axis = self._apply_deadband_curve(intent.forward_axis, self._manual_control.direction_deadband)
        turn_axis = self._apply_deadband_curve(intent.turn_axis, self._manual_control.turn_deadband)

        target.linear.x = selected_speed * forward_axis
        target.angular.z = self._manual_control.turn_rate_max_rad_s * turn_axis

        now = time.time()
        dt = max(now - self._last_manual_publish_at, 1e-3)
        twist = Twist()
        twist.linear.x = self._smooth_manual_value(
            self._last_manual_twist.linear.x,
            target.linear.x,
            self._manual_control.forward_smoothing_tau_sec,
            self._manual_control.linear_accel_limit_mps2,
            dt,
        )
        twist.angular.z = self._smooth_manual_value(
            self._last_manual_twist.angular.z,
            target.angular.z,
            self._manual_control.turn_smoothing_tau_sec,
            self._manual_control.angular_accel_limit_rad_s2,
            dt,
        )
        self._last_manual_twist = twist
        self._last_manual_publish_at = now

        self._manual_pub.publish(twist)
        bridged_to_cmd_vel = False
        if self._manual_control.direct_cmd_vel_bridge_enabled and mode.value in set(
            self._manual_control.direct_cmd_vel_bridge_modes
        ):
            self._cmd_vel_pub.publish(twist)
            bridged_to_cmd_vel = True
        details = {
            "target_linear_x": "%.3f" % target.linear.x,
            "target_angular_z": "%.3f" % target.angular.z,
            "linear_x": "%.3f" % twist.linear.x,
            "angular_z": "%.3f" % twist.angular.z,
            "speed_level": str(speed_level),
            "mode": mode.value,
            "bridged_to_cmd_vel": str(bridged_to_cmd_vel).lower(),
        }
        return ActionResult(ActionType.MANUAL_INTENT, True, "ros_ok", "manual intent published", details)

    def publish_auto_command(self, linear_x: float, angular_z: float, mode: ControlMode) -> ActionResult:
        twist = Twist()
        twist.linear.x = float(linear_x)
        twist.angular.z = float(angular_z)
        self._auto_pub.publish(twist)
        details = {
            "linear_x": "%.3f" % twist.linear.x,
            "angular_z": "%.3f" % twist.angular.z,
            "mode": mode.value,
            "bridged_to_cmd_vel": "false",
        }
        return ActionResult(ActionType.MANUAL_INTENT, True, "ros_ok", "auto command published", details)

    def _set_auto_enabled(self, enabled: bool):
        self._enable_pub.publish(Bool(data=enabled))

    def _request_stop(self, stop_requested: bool):
        self._stop_pub.publish(Bool(data=stop_requested))

    def _pulse(self, publisher, count: int, interval_sec: float):
        msg = Bool(data=True)
        for _ in range(max(count, 1)):
            publisher.publish(msg)
            if interval_sec > 0.0:
                rospy.sleep(interval_sec)

    def _publish_zero_cmds(self, duration_sec: float):
        self._reset_manual_command_filter()
        end_at = time.time() + max(duration_sec, 0.0)
        zero = Twist()
        while time.time() < end_at and not rospy.is_shutdown():
            self._manual_pub.publish(zero)
            self._auto_pub.publish(zero)
            self._cmd_vel_pub.publish(zero)
            rospy.sleep(0.05)
        self._manual_pub.publish(zero)
        self._auto_pub.publish(zero)
        self._cmd_vel_pub.publish(zero)
