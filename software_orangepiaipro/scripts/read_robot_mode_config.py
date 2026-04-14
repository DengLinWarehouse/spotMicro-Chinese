#!/usr/bin/env python3
import argparse
import os
import shlex
import sys

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required to read robot_mode_config.yaml: %s" % exc)


def as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def bool_text(value):
    return "true" if as_bool(value) else "false"


def text(value, default=""):
    if value is None:
        return default
    return str(value)


def expand_path(value):
    return os.path.expanduser(text(value))


def topic_text(value, default_topics):
    if value is None:
        topics = default_topics
    elif isinstance(value, (list, tuple)):
        topics = [text(item).strip() for item in value if text(item).strip()]
    else:
        topics = text(value).split()
    return " ".join(topics)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shell", action="store_true", help="Print shell export statements")
    parser.add_argument("mode", choices=("auto_explore_mapping", "auto_patrol"))
    parser.add_argument("config_path")
    args = parser.parse_args()

    with open(args.config_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    common = data.get("common", {})
    mode_cfg = data.get(args.mode, {})
    rplidar = common.get("rplidar", {})
    lifecycle = common.get("lifecycle", {})
    logging_cfg = common.get("logging", {})

    default_rosbag_topics = [
        text(common.get("scan_topic"), "/scan"),
        text(common.get("cmd_vel_topic"), "/cmd_vel"),
        text(common.get("cmd_vel_manual_topic"), "/cmd_vel_manual"),
        text(common.get("cmd_vel_auto_topic"), "/cmd_vel_auto"),
        text(common.get("cmd_vel_mux_topic"), "/cmd_vel_mux_raw"),
        text(common.get("stand_topic"), "/stand_cmd"),
        text(common.get("walk_topic"), "/walk_cmd"),
        text(common.get("idle_topic"), "/idle_cmd"),
        text(common.get("auto_mode_enable_topic"), "/spot_micro/auto_mode/enable"),
        text(common.get("auto_explore_stop_topic"), "/spot_micro/auto_explore/stop"),
        text(common.get("auto_state_topic"), "/spot_micro/auto_explore/state"),
        text(common.get("cmd_vel_source_topic"), "/spot_micro/cmd_vel_arbiter/source"),
        "/tf",
        "/tf_static",
        "/map",
        "/odom",
        "/rosout",
    ]

    exports = {
        "MAP_YAML": expand_path(common.get("map_yaml")),
        "SCAN_TOPIC": text(common.get("scan_topic"), "/scan"),
        "CMD_VEL_TOPIC": text(common.get("cmd_vel_topic"), "/cmd_vel"),
        "CMD_VEL_MANUAL_TOPIC": text(common.get("cmd_vel_manual_topic"), "/cmd_vel_manual"),
        "CMD_VEL_AUTO_TOPIC": text(common.get("cmd_vel_auto_topic"), "/cmd_vel_auto"),
        "CMD_VEL_MUX_TOPIC": text(common.get("cmd_vel_mux_topic"), "/cmd_vel_mux_raw"),
        "STAND_TOPIC": text(common.get("stand_topic"), "/stand_cmd"),
        "WALK_TOPIC": text(common.get("walk_topic"), "/walk_cmd"),
        "IDLE_TOPIC": text(common.get("idle_topic"), "/idle_cmd"),
        "AUTO_MODE_ENABLE_TOPIC": text(common.get("auto_mode_enable_topic"), "/spot_micro/auto_mode/enable"),
        "AUTO_EXPLORE_STOP_TOPIC": text(common.get("auto_explore_stop_topic"), "/spot_micro/auto_explore/stop"),
        "AUTO_STATE_TOPIC": text(common.get("auto_state_topic"), "/spot_micro/auto_explore/state"),
        "CMD_VEL_SOURCE_TOPIC": text(common.get("cmd_vel_source_topic"), "/spot_micro/cmd_vel_arbiter/source"),
        "LIFECYCLE_STARTUP_IDLE_ENABLED": bool_text(lifecycle.get("startup_idle_enabled", True)),
        "LIFECYCLE_STARTUP_IDLE_DELAY_SEC": text(lifecycle.get("startup_idle_delay_sec"), "0.30"),
        "LIFECYCLE_STARTUP_STAND_DELAY_SEC": text(lifecycle.get("startup_stand_delay_sec"), "1.80"),
        "LIFECYCLE_STARTUP_WALK_DELAY_SEC": text(lifecycle.get("startup_walk_delay_sec"), "1.60"),
        "LIFECYCLE_STARTUP_AUTO_ENABLE_DELAY_SEC": text(lifecycle.get("startup_auto_enable_delay_sec"), "0.80"),
        "LIFECYCLE_STARTUP_ZERO_CMD_DURATION_SEC": text(lifecycle.get("startup_zero_cmd_duration_sec"), "0.80"),
        "LIFECYCLE_SHUTDOWN_ZERO_CMD_DURATION_SEC": text(lifecycle.get("shutdown_zero_cmd_duration_sec"), "1.00"),
        "LIFECYCLE_SHUTDOWN_STAND_HOLD_SEC": text(lifecycle.get("shutdown_stand_hold_sec"), "1.20"),
        "LIFECYCLE_PULSE_COUNT": text(lifecycle.get("pulse_count"), "3"),
        "LIFECYCLE_PULSE_INTERVAL_SEC": text(lifecycle.get("pulse_interval_sec"), "0.20"),
        "RPLIDAR_SERIAL_PORT": text(rplidar.get("serial_port"), "/dev/ttyUSB0"),
        "RPLIDAR_SERIAL_BAUDRATE": text(rplidar.get("serial_baudrate"), "115200"),
        "RPLIDAR_FRAME_ID": text(rplidar.get("frame_id"), "lidar_link"),
        "RPLIDAR_INVERTED": bool_text(rplidar.get("inverted")),
        "RPLIDAR_ANGLE_COMPENSATE": bool_text(rplidar.get("angle_compensate", True)),
        "LOGGING_ENABLED": bool_text(logging_cfg.get("enabled", True)),
        "LOGGING_ROOT_DIRECTORY": expand_path(logging_cfg.get("root_directory", "~/Desktop/SpotMicro/logs")),
        "LOGGING_PANE_CAPTURE_ENABLED": bool_text(logging_cfg.get("pane_capture_enabled", True)),
        "LOGGING_ROS_LOG_ENABLED": bool_text(logging_cfg.get("ros_log_enabled", True)),
        "LOGGING_ROSBAG_ENABLED": bool_text(logging_cfg.get("rosbag_enabled", True)),
        "LOGGING_ROSBAG_OUTPUT_PREFIX": text(logging_cfg.get("rosbag_output_prefix", "spotmicro_runtime")),
        "LOGGING_ROSBAG_TOPICS": topic_text(logging_cfg.get("rosbag_topics"), default_rosbag_topics),
        "AUTOEXP_ENABLED": bool_text(mode_cfg.get("enabled", True)) if args.mode == "auto_explore_mapping" else "true",
        "AUTOEXP_AUTOSAVE_ENABLED": bool_text(mode_cfg.get("autosave_enabled", True)),
        "AUTOEXP_AUTOSAVE_INTERVAL_SEC": text(mode_cfg.get("autosave_interval_sec"), "120.0"),
        "AUTOEXP_AUTOSAVE_DIRECTORY": expand_path(mode_cfg.get("autosave_directory", "~/Desktop/SpotMicro/maps/autosave")),
        "AUTOEXP_AUTOSAVE_PREFIX": text(mode_cfg.get("autosave_prefix"), "hector_autosave"),
        "AUTOEXP_AUTOSAVE_KEEP_LAST": text(mode_cfg.get("autosave_keep_last"), "10"),
        "AUTOPATROL_ENABLED": bool_text(mode_cfg.get("enabled", True)) if args.mode == "auto_patrol" else "true",
        "AUTOPATROL_USE_MAP_SERVER": bool_text(mode_cfg.get("use_map_server", True)),
        "AUTOPATROL_USE_AMCL": bool_text(mode_cfg.get("use_amcl", False)),
    }

    if args.shell:
        for key, value in exports.items():
            print("%s=%s" % (key, shlex.quote(value)))
        return

    for key, value in exports.items():
        print("%s=%s" % (key, value))


if __name__ == "__main__":
    sys.exit(main())
