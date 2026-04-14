#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String


class CmdVelArbiter(object):
    def __init__(self):
        self.manual_topic = rospy.get_param("~manual_topic", "/cmd_vel_manual")
        self.auto_topic = rospy.get_param("~auto_topic", "/cmd_vel_auto")
        self.output_topic = rospy.get_param("~output_topic", "/cmd_vel_mux_raw")
        self.enable_topic = rospy.get_param("~enable_topic", "/spot_micro/auto_mode/enable")
        self.source_topic = rospy.get_param("~source_topic", "/spot_micro/cmd_vel_arbiter/source")

        self.manual_timeout = rospy.get_param("~manual_timeout", 0.6)
        self.auto_timeout = rospy.get_param("~auto_timeout", 0.5)
        publish_rate = rospy.get_param("~publish_rate", 20.0)
        self.auto_enabled = rospy.get_param("~auto_enabled", True)

        self.manual_cmd = Twist()
        self.auto_cmd = Twist()
        self.last_output = Twist()
        self.manual_stamp = None
        self.auto_stamp = None

        self.pub = rospy.Publisher(self.output_topic, Twist, queue_size=1)
        self.source_pub = rospy.Publisher(self.source_topic, String, queue_size=1)

        rospy.Subscriber(self.manual_topic, Twist, self._manual_cb, queue_size=1)
        rospy.Subscriber(self.auto_topic, Twist, self._auto_cb, queue_size=1)
        rospy.Subscriber(self.enable_topic, Bool, self._enable_cb, queue_size=1)

        self.timer = rospy.Timer(rospy.Duration(1.0 / publish_rate), self._tick)
        rospy.on_shutdown(self._on_shutdown)

    def _manual_cb(self, msg):
        self.manual_cmd = msg
        self.manual_stamp = rospy.Time.now()

    def _auto_cb(self, msg):
        self.auto_cmd = msg
        self.auto_stamp = rospy.Time.now()

    def _enable_cb(self, msg):
        self.auto_enabled = msg.data

    @staticmethod
    def _fresh(stamp, timeout):
        if stamp is None:
            return False
        return (rospy.Time.now() - stamp).to_sec() <= timeout

    @staticmethod
    def _zero_cmd():
        return Twist()

    def _choose_output(self):
        if self._fresh(self.manual_stamp, self.manual_timeout):
            return self.manual_cmd, "manual"

        if self.auto_enabled and self._fresh(self.auto_stamp, self.auto_timeout):
            return self.auto_cmd, "auto"

        if not self.auto_enabled:
            return self._zero_cmd(), "auto_disabled"

        return self._zero_cmd(), "idle"

    def _tick(self, _event):
        output, source = self._choose_output()
        self.last_output = output
        self.pub.publish(output)
        self.source_pub.publish(String(data=source))

    def _on_shutdown(self):
        try:
            self.pub.publish(self._zero_cmd())
            self.source_pub.publish(String(data="shutdown"))
        except rospy.ROSException:
            pass


if __name__ == "__main__":
    rospy.init_node("cmd_vel_arbiter")
    CmdVelArbiter()
    rospy.spin()
