#!/usr/bin/env python3
import rospy
from std_msgs.msg import Bool


class NavModeManager(object):
    def __init__(self):
        self.stand_topic = rospy.get_param("~stand_topic", "/stand_cmd")
        self.walk_topic = rospy.get_param("~walk_topic", "/walk_cmd")
        self.idle_topic = rospy.get_param("~idle_topic", "/idle_cmd")
        self.start_delay = rospy.get_param("~start_delay", 1.5)
        self.walk_delay = rospy.get_param("~walk_delay", 1.5)
        self.pulse_count = rospy.get_param("~pulse_count", 3)
        self.pulse_interval = rospy.get_param("~pulse_interval", 0.2)

        self.stand_pub = rospy.Publisher(self.stand_topic, Bool, queue_size=1, latch=True)
        self.walk_pub = rospy.Publisher(self.walk_topic, Bool, queue_size=1, latch=True)
        self.idle_pub = rospy.Publisher(self.idle_topic, Bool, queue_size=1, latch=True)

        rospy.Timer(rospy.Duration(self.start_delay), self._send_stand, oneshot=True)
        rospy.Timer(rospy.Duration(self.start_delay + self.walk_delay), self._send_walk, oneshot=True)
        rospy.on_shutdown(self._send_idle)

    def _pulse(self, pub):
        msg = Bool(data=True)
        for _ in range(self.pulse_count):
            pub.publish(msg)
            rospy.sleep(self.pulse_interval)

    def _send_stand(self, _event):
        rospy.loginfo("nav_mode_manager: requesting stand mode")
        self._pulse(self.stand_pub)

    def _send_walk(self, _event):
        rospy.loginfo("nav_mode_manager: requesting walk mode")
        self._pulse(self.walk_pub)

    def _send_idle(self):
        if rospy.is_shutdown():
            try:
                self.idle_pub.publish(Bool(data=True))
            except rospy.ROSException:
                pass


if __name__ == "__main__":
    rospy.init_node("nav_mode_manager")
    NavModeManager()
    rospy.spin()
