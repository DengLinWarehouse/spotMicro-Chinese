#!/usr/bin/env python3
"""Set a single servo to a specified angle.

Servo numbering is 1-based (1–16), matching the ROS i2cpwm_board convention
used in spotMicro-Chinese. Internally converted to 0-based PCA9685 channel.

Usage:
    sudo python3 set_servo.py <servo> <angle>
    sudo python3 set_servo.py 3 90          # servo 3 (LF_3 左前小腿) -> 90°
    sudo python3 set_servo.py 1 60          # servo 1 (LF_1 左前肩) -> 60° (center)
    sudo python3 set_servo.py 7 45          # servo 7 (LB_1 左后肩) -> 45°
"""

import argparse
import sys

from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685

# WARNING: All params below are for PDI-HV5523MG (120°, 900-2100µs).
# Using wrong values with a different servo may cause stall/overheating/damage.
# WARNING: All params below are for PDI-HV5523MG (120°, 900-2100µs).
# Using wrong values with a different servo may cause stall/overheating/damage.
I2C_ADDRESS = 0x40
SERVO_FREQ_HZ = 50
SERVO_MIN_US = 900       # PDI-HV5523MG: 900 µs at 0°
SERVO_MAX_US = 2100      # PDI-HV5523MG: 2100 µs at 120°
SERVO_ANGLE_RANGE = 120  # PDI-HV5523MG: 120° total travel

SERVO_MAP = {
    1:  "LF_1  左前肩",
    2:  "LF_2  左前大腿",
    3:  "LF_3  左前小腿",
    4:  "RF_1  右前肩",
    5:  "RF_2  右前大腿",
    6:  "RF_3  右前小腿",
    7:  "LB_1  左后肩",
    8:  "LB_2  左后大腿",
    9:  "LB_3  左后小腿",
    10: "RB_1  右后肩",
    11: "RB_2  右后大腿",
    12: "RB_3  右后小腿",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set a single servo to the specified angle (1-based, matches ROS config).",
    )
    parser.add_argument(
        "servo",
        type=int,
        help="Servo number (1–16, matches spot_micro_motion_cmd.yaml 'num')",
    )
    parser.add_argument(
        "angle",
        type=float,
        help="Target angle in degrees (0–120)",
    )
    parser.add_argument(
        "--address",
        type=lambda x: int(x, 0),
        default=I2C_ADDRESS,
        help="PCA9685 I2C address (default: 0x40)",
    )
    return parser.parse_args()


def angle_to_pulse_us(deg: float) -> float:
    deg = max(0.0, min(float(SERVO_ANGLE_RANGE), deg))
    return SERVO_MIN_US + (SERVO_MAX_US - SERVO_MIN_US) * (deg / SERVO_ANGLE_RANGE)


def pulse_us_to_duty(pulse_us: float, freq: float) -> int:
    period_us = 1_000_000 / freq
    duty = int((pulse_us / period_us) * 0xFFFF)
    return max(0, min(0xFFFF, duty))


def main() -> None:
    args = parse_args()

    if not 1 <= args.servo <= 16:
        print(f"Error: servo must be 1–16, got {args.servo}", file=sys.stderr)
        sys.exit(1)
    if not 0.0 <= args.angle <= SERVO_ANGLE_RANGE:
        print(f"Warning: angle {args.angle}° clamped to 0–{SERVO_ANGLE_RANGE} range", file=sys.stderr)

    hw_channel = args.servo - 1

    i2c = busio.I2C(SCL, SDA)
    pca = PCA9685(i2c, address=args.address)
    pca.frequency = SERVO_FREQ_HZ

    pulse = angle_to_pulse_us(args.angle)
    duty = pulse_us_to_duty(pulse, SERVO_FREQ_HZ)
    pca.channels[hw_channel].duty_cycle = duty

    label = SERVO_MAP.get(args.servo, "—")
    print(
        f"Servo {args.servo} [{label}] -> {args.angle:.1f}° "
        f"(~{pulse:.0f} µs, duty 0x{duty:04X}, hw_ch={hw_channel}) "
        f"at address 0x{args.address:02X}"
    )


if __name__ == "__main__":
    main()
