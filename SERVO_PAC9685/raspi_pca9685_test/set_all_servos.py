#!/usr/bin/env python3
"""Set all 16 PCA9685 channels to a fixed angle (default 60°)."""

import argparse

from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685

# WARNING: All params below are for PDI-HV5523MG (120°, 900-2100µs).
# Using wrong values with a different servo may cause stall/overheating/damage.
I2C_ADDRESS = 0x40
SERVO_FREQ_HZ = 50
SERVO_MIN_US = 900       # PDI-HV5523MG: 900 µs at 0°
SERVO_MAX_US = 2100      # PDI-HV5523MG: 2100 µs at 120°
SERVO_ANGLE_RANGE = 120  # PDI-HV5523MG: 120° total travel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set all 16 PCA9685 channels to the same angle."
    )
    parser.add_argument(
        "--angle",
        type=float,
        default=60.0,
        help="Target angle in degrees (0–120). Default: 60",
    )
    parser.add_argument(
        "--address",
        type=lambda x: int(x, 0),
        default=I2C_ADDRESS,
        help="PCA9685 I2C address (e.g. 0x40). Default: 0x40",
    )
    return parser.parse_args()


def angle_to_pulse(ang_deg: float) -> float:
    ang_deg = max(0.0, min(float(SERVO_ANGLE_RANGE), ang_deg))
    span = SERVO_MAX_US - SERVO_MIN_US
    return SERVO_MIN_US + span * (ang_deg / SERVO_ANGLE_RANGE)


def pulse_us_to_duty(pulse_us: float, freq: float) -> int:
    period_us = 1_000_000 / freq
    duty = int((pulse_us / period_us) * 0xFFFF)
    return max(0, min(0xFFFF, duty))


def main():
    args = parse_args()

    i2c = busio.I2C(SCL, SDA)
    pca = PCA9685(i2c, address=args.address)
    pca.frequency = SERVO_FREQ_HZ

    pulse = angle_to_pulse(args.angle)
    duty = pulse_us_to_duty(pulse, SERVO_FREQ_HZ)

    for ch in range(16):
        pca.channels[ch].duty_cycle = duty

    print(
        f"Set all 16 channels to {args.angle:.1f}° (~{pulse:.0f} µs, "
        f"duty 0x{duty:04X}) at address 0x{args.address:02X}"
    )


if __name__ == "__main__":
    main()
