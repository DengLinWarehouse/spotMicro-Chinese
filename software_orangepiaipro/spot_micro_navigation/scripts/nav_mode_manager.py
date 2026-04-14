#!/usr/bin/env python3
import time

import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool


class NavModeManager(object):
    def __init__(self):
        self.stand_topic = rospy.get_param("~stand_topic", "/stand_cmd")
        self.walk_topic = rospy.get_param("~walk_topic", "/walk_cmd")
        self.idle_topic = rospy.get_param("~idle_topic", "/idle_cmd")
        self.enable_topic = rospy.get_param("~enable_topic", "/spot_micro/auto_mode/enable")
        self.stop_topic = rospy.get_param("~stop_topic", "/spot_micro/auto_explore/stop")
        self.manual_cmd_topic = rospy.get_param("~manual_cmd_topic", "/cmd_vel_manual")
        self.auto_cmd_topic = rospy.get_param("~auto_cmd_topic", "/cmd_vel_auto")
        self.cmd_vel_topic = rospy.get_param("~cmd_vel_topic", "/cmd_vel")

        self.startup_idle_enabled = rospy.get_param("~startup_idle_enabled", True)
        self.startup_idle_delay_sec = rospy.get_param("~startup_idle_delay_sec", 0.30)
        self.startup_stand_delay_sec = rospy.get_param("~startup_stand_delay_sec", 1.80)
        self.startup_walk_delay_sec = rospy.get_param("~startup_walk_delay_sec", 1.60)
        self.startup_auto_enable_delay_sec = rospy.get_param("~startup_auto_enable_delay_sec", 0.80)
        self.startup_zero_cmd_duration_sec = rospy.get_param("~startup_zero_cmd_duration_sec", 0.80)
        self.shutdown_zero_cmd_duration_sec = rospy.get_param("~shutdown_zero_cmd_duration_sec", 1.00)
        self.shutdown_stand_hold_sec = rospy.get_param("~shutdown_stand_hold_sec", 1.20)
        self.pulse_count = int(rospy.get_param("~pulse_count", 3))
        self.pulse_interval_sec = rospy.get_param("~pulse_interval_sec", 0.20)
        self.auto_enable_after_walk = rospy.get_param("~auto_enable_after_walk", True)

        self.stand_pub = rospy.Publisher(self.stand_topic, Bool, queue_size=1, latch=True)
        self.walk_pub = rospy.Publisher(self.walk_topic, Bool, queue_size=1, latch=True)
        self.idle_pub = rospy.Publisher(self.idle_topic, Bool, queue_size=1, latch=True)
        self.enable_pub = rospy.Publisher(self.enable_topic, Bool, queue_size=1, latch=True)
        self.stop_pub = rospy.Publisher(self.stop_topic, Bool, queue_size=1, latch=True)
        self.manual_cmd_pub = rospy.Publisher(self.manual_cmd_topic, Twist, queue_size=1)
        self.auto_cmd_pub = rospy.Publisher(self.auto_cmd_topic, Twist, queue_size=1)
        self.cmd_vel_pub = rospy.Publisher(self.cmd_vel_topic, Twist, queue_size=1)

        self._startup_scheduled = False
        self._shutdown_started = False

        rospy.Timer(rospy.Duration(0.5), self._startup_sequence, oneshot=True)
        rospy.on_shutdown(self._on_shutdown)

    @staticmethod
    def _zero_cmd():
        return Twist()

    def _pulse(self, pub, description):
        msg = Bool(data=True)
        for _ in range(self.pulse_count):
            pub.publish(msg)
            rospy.sleep(self.pulse_interval_sec)
        rospy.loginfo("nav_mode_manager: %s", description)

    def _publish_zero_cmds(self, duration_sec):
        end_time = time.time() + max(duration_sec, 0.0)
        zero = self._zero_cmd()
        while time.time() < end_time and not rospy.is_shutdown():
            self.manual_cmd_pub.publish(zero)
            self.auto_cmd_pub.publish(zero)
            self.cmd_vel_pub.publish(zero)
            time.sleep(0.05)
        self.manual_cmd_pub.publish(zero)
        self.auto_cmd_pub.publish(zero)
        self.cmd_vel_pub.publish(zero)

    def _set_auto_enabled(self, enabled):
        self.enable_pub.publish(Bool(data=enabled))
        rospy.loginfo("nav_mode_manager: auto mode -> %s", "enabled" if enabled else "disabled")

    def _request_stop(self):
        self.stop_pub.publish(Bool(data=True))
        rospy.loginfo("nav_mode_manager: auto explore stop requested")

    def _startup_sequence(self, _event):
        if self._startup_scheduled:
            return
        self._startup_scheduled = True

        # Always enter a known safe state before asking the robot to stand and walk.
        self._set_auto_enabled(False)
        self._request_stop()
        self._publish_zero_cmds(self.startup_zero_cmd_duration_sec)

        if self.startup_idle_enabled:
            if self.startup_idle_delay_sec > 0.0:
                rospy.sleep(self.startup_idle_delay_sec)
            self._pulse(self.idle_pub, "requesting idle mode before stand")

        if self.startup_stand_delay_sec > 0.0:
            rospy.sleep(self.startup_stand_delay_sec)
        self._pulse(self.stand_pub, "requesting stand mode")

        if self.startup_walk_delay_sec > 0.0:
            rospy.sleep(self.startup_walk_delay_sec)
        self._pulse(self.walk_pub, "requesting walk mode")

        if self.auto_enable_after_walk:
            if self.startup_auto_enable_delay_sec > 0.0:
                rospy.sleep(self.startup_auto_enable_delay_sec)
            self.stop_pub.publish(Bool(data=False))
            self._set_auto_enabled(True)

    def _safe_shutdown(self):
        if self._shutdown_started:
            return
        self._shutdown_started = True

        try:
            self._set_auto_enabled(False)
            self._request_stop()
            self._publish_zero_cmds(self.shutdown_zero_cmd_duration_sec)
            self._pulse(self.stand_pub, "requesting stand mode before idle")
            if self.shutdown_stand_hold_sec > 0.0:
                time.sleep(self.shutdown_stand_hold_sec)
            self._pulse(self.idle_pub, "requesting idle mode on shutdown")
            self._publish_zero_cmds(0.20)
        except Exception:
            # Best effort only; shutdown should not crash due to cleanup failures.
            pass

    def _on_shutdown(self):
        self._safe_shutdown()


if __name__ == "__main__":
    rospy.init_node("nav_mode_manager")
    NavModeManager()
    rospy.spin()
