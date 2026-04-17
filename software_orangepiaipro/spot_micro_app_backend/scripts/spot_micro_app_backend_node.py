#!/usr/bin/env python3
import rospy

from spot_micro_app_backend.app import SpotMicroAppBackend
from spot_micro_app_backend.api_server import BackendHttpServer
from spot_micro_app_backend.models import ControlMode
from spot_micro_app_backend.ros_runtime_adapter import (
    LifecycleConfig,
    ManualControlConfig,
    RuntimeAdapterConfig,
    RuntimeAdapterTopics,
)


class SpotMicroAppBackendNode(object):
    def __init__(self):
        topics = RuntimeAdapterTopics(
            stand_topic=rospy.get_param("~topics/stand_topic", "/stand_cmd"),
            walk_topic=rospy.get_param("~topics/walk_topic", "/walk_cmd"),
            idle_topic=rospy.get_param("~topics/idle_topic", "/idle_cmd"),
            enable_topic=rospy.get_param("~topics/enable_topic", "/spot_micro/auto_mode/enable"),
            stop_topic=rospy.get_param("~topics/stop_topic", "/spot_micro/auto_explore/stop"),
            manual_cmd_topic=rospy.get_param("~topics/manual_cmd_topic", "/cmd_vel_manual"),
            auto_cmd_topic=rospy.get_param("~topics/auto_cmd_topic", "/cmd_vel_auto"),
            cmd_vel_topic=rospy.get_param("~topics/cmd_vel_topic", "/cmd_vel"),
            cmd_vel_source_topic=rospy.get_param(
                "~topics/cmd_vel_source_topic", "/spot_micro/cmd_vel_arbiter/source"
            ),
            map_topic=rospy.get_param("~topics/map_topic", "/map"),
        )
        lifecycle = LifecycleConfig(
            startup_idle_enabled=rospy.get_param("~lifecycle/startup_idle_enabled", True),
            startup_idle_delay_sec=rospy.get_param("~lifecycle/startup_idle_delay_sec", 0.30),
            startup_stand_delay_sec=rospy.get_param("~lifecycle/startup_stand_delay_sec", 1.80),
            startup_walk_delay_sec=rospy.get_param("~lifecycle/startup_walk_delay_sec", 1.60),
            startup_auto_enable_delay_sec=rospy.get_param("~lifecycle/startup_auto_enable_delay_sec", 0.80),
            startup_zero_cmd_duration_sec=rospy.get_param("~lifecycle/startup_zero_cmd_duration_sec", 0.80),
            shutdown_zero_cmd_duration_sec=rospy.get_param("~lifecycle/shutdown_zero_cmd_duration_sec", 1.00),
            shutdown_stand_hold_sec=rospy.get_param("~lifecycle/shutdown_stand_hold_sec", 1.20),
            pulse_count=int(rospy.get_param("~lifecycle/pulse_count", 3)),
            pulse_interval_sec=rospy.get_param("~lifecycle/pulse_interval_sec", 0.20),
            estop_zero_cmd_duration_sec=rospy.get_param("~lifecycle/estop_zero_cmd_duration_sec", 0.40),
        )
        manual_control = ManualControlConfig(
            speed_levels_mps=rospy.get_param("~manual_control/speed_levels_mps", [0.0, 0.03, 0.06, 0.09, 0.12]),
            turn_rate_max_rad_s=rospy.get_param("~manual_control/turn_rate_max_rad_s", 0.18),
            direction_deadband=rospy.get_param("~manual_control/direction_deadband", 0.15),
            turn_deadband=rospy.get_param("~manual_control/turn_deadband", 0.12),
            direct_cmd_vel_bridge_enabled=rospy.get_param("~manual_control/direct_cmd_vel_bridge_enabled", True),
            direct_cmd_vel_bridge_modes=rospy.get_param(
                "~manual_control/direct_cmd_vel_bridge_modes", ["MANUAL", "MANUAL_MAPPING"]
            ),
        )
        config = RuntimeAdapterConfig(
            dry_run=rospy.get_param("~dry_run", rospy.get_param("/dry_run", True)),
            health_poll_hz=rospy.get_param("~health_poll_hz", rospy.get_param("/health_poll_hz", 2.0)),
            manual_input_timeout_sec=rospy.get_param(
                "~manual_input_timeout_sec", rospy.get_param("/manual_input_timeout_sec", 0.6)
            ),
            session_timeout_sec=rospy.get_param(
                "~session_timeout_sec", rospy.get_param("/session_timeout_sec", 2.0)
            ),
            topics=topics,
            lifecycle=lifecycle,
            manual_control=manual_control,
        )
        self.backend = SpotMicroAppBackend(config)
        self.backend.state_manager.set_selected_mode(ControlMode.MANUAL)
        self.backend.refresh_health()
        period = max(1.0 / max(config.health_poll_hz, 0.1), 0.1)
        self.health_timer = rospy.Timer(rospy.Duration(period), self._health_tick)
        self.timeout_timer = rospy.Timer(rospy.Duration(0.1), self._timeout_tick)
        self.http_server = None
        if rospy.get_param("~http_server/enabled", True):
            host = rospy.get_param("~http_server/host", "0.0.0.0")
            port = int(rospy.get_param("~http_server/port", 8765))
            self.http_server = BackendHttpServer(self.backend, host=host, port=port)
            self.http_server.start()
            rospy.loginfo("spot_micro_app_backend: HTTP API listening on %s:%d", host, port)
        rospy.on_shutdown(self._on_shutdown)
        rospy.loginfo("spot_micro_app_backend: skeleton backend started (dry_run=%s)", config.dry_run)
        rospy.loginfo("spot_micro_app_backend: initial state %s", self.backend.get_status())

    def _health_tick(self, _event):
        self.backend.refresh_health()

    def _timeout_tick(self, _event):
        self.backend.process_timeouts()

    def _on_shutdown(self):
        if self.http_server is not None:
            self.http_server.stop()


if __name__ == "__main__":
    rospy.init_node("spot_micro_app_backend")
    SpotMicroAppBackendNode()
    rospy.spin()
