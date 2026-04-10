#!/usr/bin/env python3
import glob
import math
import os
import threading
from datetime import datetime

import rospy
from nav_msgs.msg import OccupancyGrid


class PeriodicMapSaver(object):
    def __init__(self):
        self.map_topic = rospy.get_param("~map_topic", "/map")
        self.save_directory = os.path.expanduser(
            rospy.get_param("~save_directory", "~/Desktop/SpotMicro/maps/autosave")
        )
        self.file_prefix = rospy.get_param("~file_prefix", "hector_autosave")
        self.interval_sec = max(rospy.get_param("~interval_sec", 120.0), 1.0)
        self.keep_last = int(rospy.get_param("~keep_last", 10))
        self.save_on_shutdown = rospy.get_param("~save_on_shutdown", True)
        self.write_latest = rospy.get_param("~write_latest", True)
        self.map_frame = rospy.get_param("~map_frame", "map")

        self.occupied_thresh = float(rospy.get_param("~occupied_thresh", 0.65))
        self.free_thresh = float(rospy.get_param("~free_thresh", 0.196))

        self._lock = threading.Lock()
        self._latest_map = None
        self._last_saved_stamp = None

        os.makedirs(self.save_directory, exist_ok=True)

        rospy.Subscriber(self.map_topic, OccupancyGrid, self._map_cb, queue_size=1)
        self._timer = rospy.Timer(rospy.Duration(self.interval_sec), self._timer_cb)
        rospy.on_shutdown(self._on_shutdown)

        rospy.loginfo(
            "periodic_map_saver: saving %s every %.1f sec into %s",
            self.map_topic,
            self.interval_sec,
            self.save_directory,
        )

    def _map_cb(self, msg):
        with self._lock:
            self._latest_map = msg

    def _timer_cb(self, _event):
        self._save_snapshot("timer")

    def _on_shutdown(self):
        if self.save_on_shutdown:
            self._save_snapshot("shutdown")

    def _snapshot_name(self, reason):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if reason:
            return "%s_%s_%s" % (self.file_prefix, reason, timestamp)
        return "%s_%s" % (self.file_prefix, timestamp)

    def _save_snapshot(self, reason):
        with self._lock:
            msg = self._latest_map

        if msg is None:
            rospy.logwarn_throttle(30.0, "periodic_map_saver: no map received yet")
            return

        stamp_key = (msg.header.stamp.secs, msg.header.stamp.nsecs)
        if reason == "timer" and stamp_key == self._last_saved_stamp:
            rospy.loginfo_throttle(30.0, "periodic_map_saver: map unchanged, skip autosave")
            return

        base_name = self._snapshot_name(reason)
        base_path = os.path.join(self.save_directory, base_name)

        try:
            self._write_map(msg, base_path)
            self._last_saved_stamp = stamp_key
            rospy.loginfo("periodic_map_saver: saved %s.{pgm,yaml}", base_path)

            if self.write_latest:
                latest_base = os.path.join(self.save_directory, self.file_prefix + "_latest")
                self._write_map(msg, latest_base)

            self._prune_old_snapshots()
        except Exception as exc:
            rospy.logerr("periodic_map_saver: save failed: %s", exc)

    def _prune_old_snapshots(self):
        if self.keep_last <= 0:
            return

        pattern = os.path.join(self.save_directory, self.file_prefix + "_*.yaml")
        yaml_files = sorted(glob.glob(pattern))

        timestamped = [
            path
            for path in yaml_files
            if not path.endswith("_latest.yaml")
        ]

        while len(timestamped) > self.keep_last:
            yaml_path = timestamped.pop(0)
            pgm_path = yaml_path[:-5] + ".pgm"
            if os.path.exists(yaml_path):
                os.remove(yaml_path)
            if os.path.exists(pgm_path):
                os.remove(pgm_path)

    def _write_map(self, msg, base_path):
        pgm_path = base_path + ".pgm"
        yaml_path = base_path + ".yaml"

        width = msg.info.width
        height = msg.info.height
        data = msg.data

        with open(pgm_path, "wb") as pgm:
            pgm.write(("P5\n# CREATOR: periodic_map_saver.py %.3f m/pix\n" % msg.info.resolution).encode("ascii"))
            pgm.write(("%d %d\n255\n" % (width, height)).encode("ascii"))

            for y in range(height):
                row = height - y - 1
                for x in range(width):
                    value = data[row * width + x]
                    pgm.write(bytes((self._occupancy_to_pixel(value),)))

        yaw = self._yaw_from_quaternion(msg.info.origin.orientation)
        image_name = os.path.basename(pgm_path)

        with open(yaml_path, "w", encoding="ascii") as yaml_file:
            yaml_file.write("image: %s\n" % image_name)
            yaml_file.write("resolution: %.12g\n" % msg.info.resolution)
            yaml_file.write(
                "origin: [%.12g, %.12g, %.12g]\n"
                % (msg.info.origin.position.x, msg.info.origin.position.y, yaw)
            )
            yaml_file.write("negate: 0\n")
            yaml_file.write("occupied_thresh: %.3f\n" % self.occupied_thresh)
            yaml_file.write("free_thresh: %.3f\n" % self.free_thresh)

    def _occupancy_to_pixel(self, value):
        if value < 0:
            return 205
        if value >= int(self.occupied_thresh * 100.0):
            return 0
        if value <= int(self.free_thresh * 100.0):
            return 254
        return 205

    @staticmethod
    def _yaw_from_quaternion(quat):
        siny_cosp = 2.0 * (quat.w * quat.z + quat.x * quat.y)
        cosy_cosp = 1.0 - 2.0 * (quat.y * quat.y + quat.z * quat.z)
        return math.atan2(siny_cosp, cosy_cosp)


if __name__ == "__main__":
    rospy.init_node("periodic_map_saver")
    PeriodicMapSaver()
    rospy.spin()
