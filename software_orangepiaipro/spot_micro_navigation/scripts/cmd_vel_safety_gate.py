#!/usr/bin/env python3
import math

import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PoseWithCovarianceStamped


class CmdVelSafetyGate(object):
    def __init__(self):
        self.input_topic = rospy.get_param("~input_topic", "/cmd_vel_nav_raw")
        self.output_topic = rospy.get_param("~output_topic", "/cmd_vel")
        self.scan_topic = rospy.get_param("~scan_topic", "/scan")
        self.amcl_pose_topic = rospy.get_param("~amcl_pose_topic", "/amcl_pose")

        self.scan_timeout = rospy.get_param("~scan_timeout", 0.30)
        self.cmd_timeout = rospy.get_param("~cmd_timeout", 0.50)
        self.amcl_timeout = rospy.get_param("~amcl_timeout", 1.00)

        self.front_sector_deg = rospy.get_param("~front_sector_deg", 20.0)
        self.front_stop_distance = rospy.get_param("~front_stop_distance", 0.35)

        self.max_cov_x = rospy.get_param("~max_cov_x", 0.20)
        self.max_cov_y = rospy.get_param("~max_cov_y", 0.20)
        self.max_cov_yaw = rospy.get_param("~max_cov_yaw", 0.35)

        self.max_vx = rospy.get_param("~max_vx", 0.12)
        self.max_vy = rospy.get_param("~max_vy", 0.00)
        self.max_wz = rospy.get_param("~max_wz", 0.20)

        self.accel_vx = rospy.get_param("~accel_vx", 0.20)
        self.accel_vy = rospy.get_param("~accel_vy", 0.00)
        self.accel_wz = rospy.get_param("~accel_wz", 0.35)
        publish_rate = rospy.get_param("~publish_rate", 20.0)

        self.last_cmd = Twist()
        self.last_scan = None
        self.last_amcl = None
        self.last_output = Twist()
        self.last_tick = rospy.Time.now()

        self.cmd_stamp = None
        self.scan_stamp = None
        self.amcl_stamp = None

        self.pub = rospy.Publisher(self.output_topic, Twist, queue_size=1)
        rospy.Subscriber(self.input_topic, Twist, self._cmd_cb, queue_size=1)
        rospy.Subscriber(self.scan_topic, LaserScan, self._scan_cb, queue_size=1)
        rospy.Subscriber(self.amcl_pose_topic, PoseWithCovarianceStamped, self._amcl_cb, queue_size=1)

        self.timer = rospy.Timer(rospy.Duration(1.0 / publish_rate), self._tick)

    def _cmd_cb(self, msg):
        self.last_cmd = msg
        self.cmd_stamp = rospy.Time.now()

    def _scan_cb(self, msg):
        self.last_scan = msg
        self.scan_stamp = rospy.Time.now()

    def _amcl_cb(self, msg):
        self.last_amcl = msg
        self.amcl_stamp = rospy.Time.now()

    def _fresh(self, stamp, timeout):
        if stamp is None:
            return False
        return (rospy.Time.now() - stamp).to_sec() <= timeout

    def _front_blocked(self):
        if self.last_scan is None:
            return True

        half_sector = math.radians(self.front_sector_deg)
        angle = self.last_scan.angle_min
        blocked = False

        for value in self.last_scan.ranges:
            if -half_sector <= angle <= half_sector:
                if math.isfinite(value) and self.last_scan.range_min <= value <= self.front_stop_distance:
                    blocked = True
                    break
            angle += self.last_scan.angle_increment
        return blocked

    def _amcl_ok(self):
        if self.last_amcl is None:
            return False
        cov = self.last_amcl.pose.covariance
        return cov[0] <= self.max_cov_x and cov[7] <= self.max_cov_y and cov[35] <= self.max_cov_yaw

    @staticmethod
    def _clamp(value, limit):
        if value > limit:
            return limit
        if value < -limit:
            return -limit
        return value

    @staticmethod
    def _limit_rate(target, current, accel, dt):
        if accel <= 0.0:
            return target
        delta = target - current
        max_delta = accel * dt
        if delta > max_delta:
            return current + max_delta
        if delta < -max_delta:
            return current - max_delta
        return target

    def _unsafe(self):
        if not self._fresh(self.scan_stamp, self.scan_timeout):
            rospy.logwarn_throttle(1.0, "cmd_vel_safety_gate: scan timed out")
            return True
        if not self._fresh(self.cmd_stamp, self.cmd_timeout):
            return True
        if not self._fresh(self.amcl_stamp, self.amcl_timeout):
            rospy.logwarn_throttle(1.0, "cmd_vel_safety_gate: AMCL timed out")
            return True
        if not self._amcl_ok():
            rospy.logwarn_throttle(1.0, "cmd_vel_safety_gate: AMCL covariance too large")
            return True
        if self.last_cmd.linear.x > 0.0 and self._front_blocked():
            rospy.logwarn_throttle(1.0, "cmd_vel_safety_gate: front obstacle stop")
            return True
        return False

    def _tick(self, _event):
        now = rospy.Time.now()
        dt = max((now - self.last_tick).to_sec(), 1e-3)
        self.last_tick = now

        target = Twist()
        if not self._unsafe():
            target.linear.x = self._clamp(self.last_cmd.linear.x, self.max_vx)
            target.linear.y = self._clamp(self.last_cmd.linear.y, self.max_vy)
            target.angular.z = self._clamp(self.last_cmd.angular.z, self.max_wz)

        output = Twist()
        output.linear.x = self._limit_rate(target.linear.x, self.last_output.linear.x, self.accel_vx, dt)
        output.linear.y = self._limit_rate(target.linear.y, self.last_output.linear.y, self.accel_vy, dt)
        output.angular.z = self._limit_rate(target.angular.z, self.last_output.angular.z, self.accel_wz, dt)

        self.last_output = output
        self.pub.publish(output)


if __name__ == "__main__":
    rospy.init_node("cmd_vel_safety_gate")
    CmdVelSafetyGate()
    rospy.spin()
