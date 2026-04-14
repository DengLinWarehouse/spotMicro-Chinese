#!/usr/bin/env python3
import argparse
import os
import time

import rospy
import yaml
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool


def load_config(config_path):
    with open(config_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def text(value, default=""):
    if value is None:
        return default
    return str(value)


def as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def zero_cmd():
    return Twist()


def pulse(pub, count, interval_sec):
    msg = Bool(data=True)
    for _ in range(count):
        pub.publish(msg)
        time.sleep(interval_sec)


def publish_zero(pub_list, duration_sec):
    end_time = time.time() + max(duration_sec, 0.0)
    zero = zero_cmd()
    while time.time() < end_time and not rospy.is_shutdown():
        for pub in pub_list:
            pub.publish(zero)
        time.sleep(0.05)
    for pub in pub_list:
        pub.publish(zero)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(os.path.expanduser(args.config))
    common = config.get("common", {})
    lifecycle = common.get("lifecycle", {})

    stand_topic = text(common.get("stand_topic"), "/stand_cmd")
    walk_topic = text(common.get("walk_topic"), "/walk_cmd")
    idle_topic = text(common.get("idle_topic"), "/idle_cmd")
    enable_topic = text(common.get("auto_mode_enable_topic"), "/spot_micro/auto_mode/enable")
    stop_topic = text(common.get("auto_explore_stop_topic"), "/spot_micro/auto_explore/stop")
    cmd_vel_topic = text(common.get("cmd_vel_topic"), "/cmd_vel")
    cmd_vel_manual_topic = text(common.get("cmd_vel_manual_topic"), "/cmd_vel_manual")
    cmd_vel_auto_topic = text(common.get("cmd_vel_auto_topic"), "/cmd_vel_auto")
    zero_duration = float(lifecycle.get("shutdown_zero_cmd_duration_sec", 1.00))
    stand_hold = float(lifecycle.get("shutdown_stand_hold_sec", 1.20))
    pulse_count = int(lifecycle.get("pulse_count", 3))
    pulse_interval = float(lifecycle.get("pulse_interval_sec", 0.20))

    rospy.init_node("safe_stop_robot", anonymous=True)

    stand_pub = rospy.Publisher(stand_topic, Bool, queue_size=1, latch=True)
    walk_pub = rospy.Publisher(walk_topic, Bool, queue_size=1, latch=True)
    idle_pub = rospy.Publisher(idle_topic, Bool, queue_size=1, latch=True)
    enable_pub = rospy.Publisher(enable_topic, Bool, queue_size=1, latch=True)
    stop_pub = rospy.Publisher(stop_topic, Bool, queue_size=1, latch=True)
    cmd_vel_pub = rospy.Publisher(cmd_vel_topic, Twist, queue_size=1)
    cmd_vel_manual_pub = rospy.Publisher(cmd_vel_manual_topic, Twist, queue_size=1)
    cmd_vel_auto_pub = rospy.Publisher(cmd_vel_auto_topic, Twist, queue_size=1)

    time.sleep(0.4)

    enable_pub.publish(Bool(data=False))
    stop_pub.publish(Bool(data=True))
    walk_pub.publish(Bool(data=False))
    publish_zero([cmd_vel_pub, cmd_vel_manual_pub, cmd_vel_auto_pub], zero_duration)
    pulse(stand_pub, pulse_count, pulse_interval)
    if stand_hold > 0.0:
        time.sleep(stand_hold)
    pulse(idle_pub, pulse_count, pulse_interval)
    publish_zero([cmd_vel_pub, cmd_vel_manual_pub, cmd_vel_auto_pub], 0.20)


if __name__ == "__main__":
    main()
