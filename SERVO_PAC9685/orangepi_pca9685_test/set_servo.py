#!/usr/bin/env python3
"""Set a single servo to a specified angle on OrangePi AI Pro.

Uses smbus2 to communicate directly via /dev/i2c-7.
No adafruit-blinka dependency, no ROS required.

Usage:
    sudo python3 set_servo.py <servo> <angle>
    sudo python3 set_servo.py 3 90          # servo 3 (LF_3 左前小腿) -> 90°
    sudo python3 set_servo.py 1 60          # servo 1 (LF_1 左前肩) -> 60° (center)
"""

import argparse
import sys
import time

# PCA9685 Register definitions
MODE1       = 0x00
PRESCALE    = 0xFE
CHANNEL_ON_L  = 0x06
CHANNEL_OFF_L = 0x08

I2C_ADDRESS  = 0x40
I2C_BUS      = 7   # /dev/i2c-7 (OrangePi AI Pro 40-pin header)
SERVO_FREQ_HZ = 50

# For PDI-HV5523MG servo (120deg, 900-2100us)
SERVO_MIN_US  = 900
SERVO_MAX_US  = 2100
SERVO_RANGE_US = SERVO_MAX_US - SERVO_MIN_US  # 1200 us

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


def angle_to_pulse(deg: float) -> float:
    """Convert angle (0-120) to pulse width in microseconds."""
    return SERVO_MIN_US + SERVO_RANGE_US * (deg / 120.0)


def pulse_us_to_pwm(pulse_us: float) -> int:
    """Convert microseconds to PCA9685 PWM value (0-4095)."""
    period_us = 1_000_000 / SERVO_FREQ_HZ
    pwm = int((pulse_us / period_us) * 4096)
    return max(0, min(4095, pwm))


def set_servo_pwm(bus, channel: int, pwm_val: int):
    """Set a single channel PWM value (0-4095)."""
    reg_on_l  = CHANNEL_ON_L  + 4 * channel
    reg_off_l = CHANNEL_OFF_L + 4 * channel
    bus.write_i2c_block_data(I2C_ADDRESS, reg_on_l,  [0x00, 0x00])
    bus.write_i2c_block_data(I2C_ADDRESS, reg_off_l,
                             [pwm_val & 0xFF, (pwm_val >> 8) & 0xFF])


def init_pca9685(bus):
    """Initialize PCA9685 with 50Hz PWM frequency."""
    # Wake from sleep
    mode1 = bus.read_byte_data(I2C_ADDRESS, MODE1)
    bus.write_byte_data(I2C_ADDRESS, MODE1, mode1 & ~0x10)

    # Set prescale for 50Hz
    prescale = int(round(25_000_000 / (4096 * SERVO_FREQ_HZ))) - 1
    bus.write_byte_data(I2C_ADDRESS, MODE1, mode1 | 0x10)  # Sleep to set freq
    bus.write_byte_data(I2C_ADDRESS, PRESCALE, max(3, min(255, prescale)))
    bus.write_byte_data(I2C_ADDRESS, MODE1, mode1 & ~0x10)  # Wake
    time.sleep(0.005)


def main():
    parser = argparse.ArgumentParser(
        description="Set a single servo to the specified angle (1-based, matches ROS config).",
    )
    parser.add_argument(
        "servo", type=int,
        help="Servo number (1–12, matches spot_micro_motion_cmd.yaml 'num')",
    )
    parser.add_argument(
        "angle", type=float,
        help="Target angle in degrees (0–120)",
    )
    parser.add_argument(
        "--address", type=lambda x: int(x, 0), default=I2C_ADDRESS,
        help="PCA9685 I2C address (default: 0x40)",
    )
    args = parser.parse_args()

    if not 1 <= args.servo <= 12:
        print(f"ERROR: servo must be 1–12, got {args.servo}", file=sys.stderr)
        sys.exit(1)
    if args.angle < 0 or args.angle > 120:
        print(f"WARNING: angle {args.angle}° is outside 0–120 range",
              file=sys.stderr)

    hw_channel = args.servo - 1  # 1-based -> 0-based
    pulse = angle_to_pulse(args.angle)
    pwm = pulse_us_to_pwm(pulse)

    label = SERVO_MAP.get(args.servo, "—")
    print(f"Servo {args.servo} [{label}] -> {args.angle:.1f}° "
          f"(~{pulse:.0f} us, PWM={pwm}, ch={hw_channel}) "
          f"bus=/dev/i2c-{I2C_BUS} addr=0x{args.address:02X}")

    try:
        from smbus2 import SMBus
    except ImportError:
        print("ERROR: smbus2 not installed.", file=sys.stderr)
        print("Run:  pip install smbus2", file=sys.stderr)
        sys.exit(1)

    with SMBus(I2C_BUS) as bus:
        init_pca9685(bus)
        set_servo_pwm(bus, hw_channel, pwm)

    print("Done.")


if __name__ == "__main__":
    main()
