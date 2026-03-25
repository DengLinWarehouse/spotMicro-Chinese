#!/usr/bin/env python3
"""Set all 16 PCA9685 channels to a fixed angle on OrangePi AI Pro.

Uses smbus2 to communicate directly via /dev/i2c-7.
No adafruit-blinka dependency, no ROS required.

Usage:
    sudo python3 set_all_servos.py                    # all to 60deg (center)
    sudo python3 set_all_servos.py --angle 0        # all to 0deg
    sudo python3 set_all_servos.py --angle 120      # all to 120deg
    sudo python3 set_all_servos.py --address 0x41   # different PCA9685 address
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
I2C_BUS      = 7
SERVO_FREQ_HZ = 50

# For PDI-HV5523MG servo (120deg, 900-2100us)
SERVO_MIN_US  = 900
SERVO_MAX_US  = 2100
SERVO_RANGE_US = SERVO_MAX_US - SERVO_MIN_US


def angle_to_pulse(deg: float) -> float:
    return SERVO_MIN_US + SERVO_RANGE_US * (deg / 120.0)


def pulse_us_to_pwm(pulse_us: float) -> int:
    period_us = 1_000_000 / SERVO_FREQ_HZ
    pwm = int((pulse_us / period_us) * 4096)
    return max(0, min(4095, pwm))


def set_servo_pwm(bus, channel: int, pwm_val: int):
    reg_on_l  = CHANNEL_ON_L  + 4 * channel
    reg_off_l = CHANNEL_OFF_L + 4 * channel
    bus.write_i2c_block_data(I2C_ADDRESS, reg_on_l,  [0x00, 0x00])
    bus.write_i2c_block_data(I2C_ADDRESS, reg_off_l,
                             [pwm_val & 0xFF, (pwm_val >> 8) & 0xFF])


def init_pca9685(bus):
    mode1 = bus.read_byte_data(I2C_ADDRESS, MODE1)
    bus.write_byte_data(I2C_ADDRESS, MODE1, mode1 & ~0x10)
    prescale = int(round(25_000_000 / (4096 * SERVO_FREQ_HZ))) - 1
    bus.write_byte_data(I2C_ADDRESS, MODE1, mode1 | 0x10)
    bus.write_byte_data(I2C_ADDRESS, PRESCALE, max(3, min(255, prescale)))
    bus.write_byte_data(I2C_ADDRESS, MODE1, mode1 & ~0x10)
    time.sleep(0.005)


def main():
    parser = argparse.ArgumentParser(
        description="Set all 16 PCA9685 channels to the same angle.",
    )
    parser.add_argument(
        "--angle", type=float, default=60.0,
        help="Target angle in degrees (0–120). Default: 60",
    )
    parser.add_argument(
        "--address", type=lambda x: int(x, 0), default=I2C_ADDRESS,
        help="PCA9685 I2C address (default: 0x40)",
    )
    args = parser.parse_args()

    pulse = angle_to_pulse(args.angle)
    pwm = pulse_us_to_pwm(pulse)
    print(f"Setting all 16 channels to {args.angle:.1f}deg "
          f"({pulse:.0f}us, PWM={pwm}) "
          f"bus=/dev/i2c-{I2C_BUS} addr=0x{args.address:02X}")

    try:
        from smbus2 import SMBus
    except ImportError:
        print("ERROR: smbus2 not installed.", file=sys.stderr)
        print("Run:  pip install smbus2", file=sys.stderr)
        sys.exit(1)

    with SMBus(I2C_BUS) as bus:
        init_pca9685(bus)
        for ch in range(16):
            set_servo_pwm(bus, ch, pwm)
        print("All servos set.")

    print("Done.")


if __name__ == "__main__":
    main()
