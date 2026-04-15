#!/usr/bin/env python3
import math
import random
import statistics

import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String


class LaserWanderExplorer(object):
    FORWARD = "FORWARD"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"
    ESCAPE = "ESCAPE"
    STOP = "STOP"

    def __init__(self):
        self.scan_topic = rospy.get_param("~scan_topic", "/scan")
        self.output_topic = rospy.get_param("~output_topic", "/cmd_vel_auto")
        self.enable_topic = rospy.get_param("~enable_topic", "/spot_micro/auto_mode/enable")
        self.stop_topic = rospy.get_param("~stop_topic", "/spot_micro/auto_explore/stop")
        self.state_topic = rospy.get_param("~state_topic", "/spot_micro/auto_explore/state")

        self.enabled = rospy.get_param("~enabled", True)
        self.scan_timeout = rospy.get_param("~scan_timeout", 0.30)
        self.cmd_rate = rospy.get_param("~cmd_rate", 10.0)

        self.cruise_speed = rospy.get_param("~cruise_speed", 0.06)
        self.turn_speed = rospy.get_param("~turn_speed", 0.22)
        self.forward_safe_dist = rospy.get_param("~forward_safe_dist", 0.60)
        self.turn_trigger_dist = rospy.get_param("~turn_trigger_dist", 0.42)
        self.turn_trigger_min_margin = rospy.get_param("~turn_trigger_min_margin", 0.10)
        # Original logic entered TURN_* as soon as the current scan looked blocked.
        # Keep the same distance trigger, but require a few consecutive blocked cycles
        # before committing to a turn so scan jitter does not thrash the gait layer.
        self.obstacle_confirm_cycles = int(rospy.get_param("~obstacle_confirm_cycles", 3))
        # Recover from TURN_* only after a sustained clear view. This creates hysteresis
        # between "enter turn" and "resume forward" so the robot does not bounce states.
        self.clear_confirm_cycles = int(rospy.get_param("~clear_confirm_cycles", 6))
        self.turn_release_dist = rospy.get_param("~turn_release_dist", 0.62)
        self.turn_release_min_margin = rospy.get_param("~turn_release_min_margin", 0.08)
        self.stuck_dist = rospy.get_param("~stuck_dist", 0.30)
        self.stuck_side_dist = rospy.get_param("~stuck_side_dist", 0.28)

        self.front_center_deg = rospy.get_param("~front_center_deg", 20.0)
        self.front_left_min_deg = rospy.get_param("~front_left_min_deg", 20.0)
        self.front_left_max_deg = rospy.get_param("~front_left_max_deg", 70.0)
        self.front_right_min_deg = rospy.get_param("~front_right_min_deg", -70.0)
        self.front_right_max_deg = rospy.get_param("~front_right_max_deg", -20.0)

        self.turn_duration_sec = rospy.get_param("~turn_duration_sec", 0.90)
        self.turn_duration_jitter_sec = rospy.get_param("~turn_duration_jitter_sec", 0.30)
        # Even if the front briefly looks clear, keep a minimum turn commitment so the
        # robot can finish a meaningful heading change before reconsidering FORWARD.
        self.min_turn_commit_sec = rospy.get_param("~min_turn_commit_sec", 0.80)
        self.escape_turn_duration_sec = rospy.get_param("~escape_turn_duration_sec", 1.30)
        self.escape_pause_sec = rospy.get_param("~escape_pause_sec", 0.25)
        self.stuck_cycles_threshold = int(rospy.get_param("~stuck_cycles_threshold", 8))
        self.turn_hold_cycles_threshold = int(rospy.get_param("~turn_hold_cycles_threshold", 20))

        self.random_turn_bias = rospy.get_param("~random_turn_bias", 0.04)
        self.side_balance_gain = rospy.get_param("~side_balance_gain", 0.15)
        self.bias_refresh_sec = rospy.get_param("~bias_refresh_sec", 1.5)

        self.last_scan = None
        self.scan_stamp = None
        self.state = self.STOP
        self.state_until = rospy.Time(0)
        self.pause_until = rospy.Time(0)
        # Match spotMicroKeyboardMove.py yaw convention:
        # negative -> left turn, positive -> right turn.
        self.last_turn_sign = 1.0
        self.forward_bias = 0.0
        self.bias_refresh_at = rospy.Time.now()
        self.blocked_cycles = 0
        self.clear_cycles = 0
        self.turn_hold_cycles = 0

        self.pub = rospy.Publisher(self.output_topic, Twist, queue_size=1)
        self.state_pub = rospy.Publisher(self.state_topic, String, queue_size=1)

        rospy.Subscriber(self.scan_topic, LaserScan, self._scan_cb, queue_size=1)
        rospy.Subscriber(self.enable_topic, Bool, self._enable_cb, queue_size=1)
        rospy.Subscriber(self.stop_topic, Bool, self._stop_cb, queue_size=1)

        self.timer = rospy.Timer(rospy.Duration(1.0 / self.cmd_rate), self._tick)
        rospy.on_shutdown(self._on_shutdown)

    def _scan_cb(self, msg):
        self.last_scan = msg
        self.scan_stamp = rospy.Time.now()

    def _enable_cb(self, msg):
        self.enabled = msg.data
        if self.enabled:
            self._set_state(self.FORWARD)
        else:
            self._set_state(self.STOP)

    def _stop_cb(self, msg):
        if msg.data:
            self.enabled = False
            self._set_state(self.STOP)

    @staticmethod
    def _zero_cmd():
        return Twist()

    def _scan_fresh(self):
        if self.scan_stamp is None:
            return False
        return (rospy.Time.now() - self.scan_stamp).to_sec() <= self.scan_timeout

    def _set_state(self, state, hold_sec=0.0):
        self.state = state
        self.state_until = rospy.Time.now() + rospy.Duration(max(hold_sec, 0.0))
        if state in (self.TURN_LEFT, self.TURN_RIGHT, self.ESCAPE):
            self.turn_hold_cycles += 1
        else:
            self.turn_hold_cycles = 0

    def _sector_samples(self, scan, min_deg, max_deg):
        min_rad = math.radians(min_deg)
        max_rad = math.radians(max_deg)
        values = []
        angle = scan.angle_min

        for value in scan.ranges:
            if min_rad <= angle <= max_rad:
                if math.isfinite(value) and scan.range_min <= value <= scan.range_max:
                    values.append(value)
            angle += scan.angle_increment

        return values

    @staticmethod
    def _sector_stats(values):
        if not values:
            return 0.0, 0.0
        return min(values), statistics.median(values)

    def _scan_view(self):
        scan = self.last_scan
        front = self._sector_samples(scan, -self.front_center_deg, self.front_center_deg)
        front_left = self._sector_samples(scan, self.front_left_min_deg, self.front_left_max_deg)
        front_right = self._sector_samples(scan, self.front_right_min_deg, self.front_right_max_deg)

        front_min, front_med = self._sector_stats(front)
        left_min, left_med = self._sector_stats(front_left)
        right_min, right_med = self._sector_stats(front_right)

        return {
            "front_min": front_min,
            "front_med": front_med,
            "left_min": left_min,
            "left_med": left_med,
            "right_min": right_min,
            "right_med": right_med,
        }

    def _choose_turn_sign(self, view):
        if view["left_med"] > view["right_med"]:
            return -1.0
        if view["right_med"] > view["left_med"]:
            return 1.0
        return self.last_turn_sign

    def _turn_hold_sec(self):
        jitter = random.uniform(-self.turn_duration_jitter_sec, self.turn_duration_jitter_sec)
        return max(self.min_turn_commit_sec, self.turn_duration_sec + jitter)

    @staticmethod
    def _clamp(value, limit):
        if value > limit:
            return limit
        if value < -limit:
            return -limit
        return value

    def _forward_bias_cmd(self, view):
        if rospy.Time.now() >= self.bias_refresh_at:
            self.forward_bias = random.uniform(-self.random_turn_bias, self.random_turn_bias)
            self.bias_refresh_at = rospy.Time.now() + rospy.Duration(self.bias_refresh_sec)

        balance = (view["right_med"] - view["left_med"]) * self.side_balance_gain
        return self._clamp(balance + self.forward_bias, self.turn_speed * 0.35)

    def _forward_speed_cmd(self, view):
        front = view["front_med"]
        if front <= self.turn_trigger_dist:
            return 0.0
        if front >= self.forward_safe_dist:
            return self.cruise_speed

        span = max(self.forward_safe_dist - self.turn_trigger_dist, 1e-3)
        ratio = (front - self.turn_trigger_dist) / span
        ratio = self._clamp(ratio, 1.0)
        return max(0.02, self.cruise_speed * ratio)

    def _front_clear(self, view):
        release_min = max(
            self.turn_trigger_dist,
            self.turn_release_dist - self.turn_release_min_margin,
        )
        return (
            view["front_med"] >= self.turn_release_dist
            and view["front_min"] >= release_min
        )

    def _enter_turn_state(self, turn_sign):
        self.last_turn_sign = turn_sign
        if turn_sign < 0.0:
            self._set_state(self.TURN_LEFT, self._turn_hold_sec())
        else:
            self._set_state(self.TURN_RIGHT, self._turn_hold_sec())

    def _enter_escape_state(self, turn_sign):
        self.last_turn_sign = turn_sign
        self.pause_until = rospy.Time.now() + rospy.Duration(self.escape_pause_sec)
        self._set_state(self.ESCAPE, self.escape_turn_duration_sec)
        self.blocked_cycles = 0

    def _publish_state(self, view):
        msg = "%s front=%.2f left=%.2f right=%.2f enabled=%s" % (
            self.state,
            view.get("front_med", 0.0),
            view.get("left_med", 0.0),
            view.get("right_med", 0.0),
            str(self.enabled).lower(),
        )
        self.state_pub.publish(String(data=msg))

    def _tick(self, _event):
        output = self._zero_cmd()
        view = {}

        if not self.enabled:
            self._set_state(self.STOP)
        elif not self._scan_fresh():
            self._set_state(self.STOP)
        else:
            view = self._scan_view()

            # Use both the sector median and the nearest point so the explorer
            # starts turning before the safety gate fully blocks forward motion.
            front_close = (
                view["front_med"] <= self.turn_trigger_dist
                or view["front_min"] <= max(self.stuck_dist, self.turn_trigger_dist - self.turn_trigger_min_margin)
            )
            escape_needed = (
                view["front_med"] < self.stuck_dist
                and view["left_med"] < self.stuck_side_dist
                and view["right_med"] < self.stuck_side_dist
            )

            if front_close:
                self.blocked_cycles += 1
            else:
                self.blocked_cycles = 0

            if self._front_clear(view):
                self.clear_cycles += 1
            else:
                self.clear_cycles = 0

            if self.state in (self.TURN_LEFT, self.TURN_RIGHT, self.ESCAPE) and rospy.Time.now() < self.state_until:
                pass
            elif escape_needed or self.blocked_cycles >= self.stuck_cycles_threshold or self.turn_hold_cycles >= self.turn_hold_cycles_threshold:
                turn_sign = -self.last_turn_sign if self.last_turn_sign != 0.0 else self._choose_turn_sign(view)
                self._enter_escape_state(turn_sign)
            else:
                in_turn_state = self.state in (self.TURN_LEFT, self.TURN_RIGHT, self.ESCAPE)

                # Original behavior:
                #   elif front_close:
                #       self._enter_turn_state(self._choose_turn_sign(view))
                #   else:
                #       self._set_state(self.FORWARD)
                #
                # Updated behavior:
                #   - require sustained obstacle confirmation before entering TURN_*
                #   - require sustained clearance before leaving TURN_*
                #   - keep the current turn if the scan is still ambiguous
                if in_turn_state:
                    if self.clear_cycles >= self.clear_confirm_cycles:
                        self._set_state(self.FORWARD)
                    elif front_close and self.blocked_cycles >= self.obstacle_confirm_cycles:
                        # Refresh the turn with the existing preferred sign so the
                        # robot keeps rotating through ambiguous scan intervals.
                        turn_sign = self.last_turn_sign if self.last_turn_sign != 0.0 else self._choose_turn_sign(view)
                        if self.state == self.ESCAPE:
                            self.last_turn_sign = turn_sign
                            self._set_state(self.ESCAPE, self.escape_turn_duration_sec)
                        else:
                            self._enter_turn_state(turn_sign)
                elif front_close and self.blocked_cycles >= self.obstacle_confirm_cycles:
                    self._enter_turn_state(self._choose_turn_sign(view))
                else:
                    self._set_state(self.FORWARD)

            if self.state == self.FORWARD:
                output.linear.x = self._forward_speed_cmd(view)
                output.angular.z = self._forward_bias_cmd(view)
            elif self.state == self.TURN_LEFT:
                output.angular.z = -abs(self.turn_speed)
            elif self.state == self.TURN_RIGHT:
                output.angular.z = abs(self.turn_speed)
            elif self.state == self.ESCAPE:
                if rospy.Time.now() >= self.pause_until:
                    output.angular.z = abs(self.turn_speed) if self.last_turn_sign > 0.0 else -abs(self.turn_speed)
            else:
                output = self._zero_cmd()

        self.pub.publish(output)
        self._publish_state(view)

    def _on_shutdown(self):
        try:
            self.pub.publish(self._zero_cmd())
            self.state_pub.publish(String(data="STOP shutdown=true"))
        except rospy.ROSException:
            pass


if __name__ == "__main__":
    rospy.init_node("laser_wander_explorer")
    LaserWanderExplorer()
    rospy.spin()
