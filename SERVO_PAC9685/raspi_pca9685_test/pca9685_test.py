#!/usr/bin/env python3
"""Simple PCA9685 servo sweep demo for Raspberry Pi.

Matches logic from SERVO2_PCA9685.ino but uses CircuitPython library.
"""
import time
from typing import Tuple

from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685

# WARNING: Pulse width params are for PDI-HV5523MG (120°, 900-2100µs).
# Using wrong values with a different servo may cause stall/overheating/damage.
I2C_ADDRESS = 0x40
SERVO_FREQ_HZ = 50
SERVO_MIN_US = 900       # PDI-HV5523MG: 900 µs at 0°
SERVO_MAX_US = 2100      # PDI-HV5523MG: 2100 µs at 120°
SLEEP_SEC = 0.5


def pulse_us_to_duty(pulse_us: float, freq: float) -> int:
    period_us = 1_000_000 / freq
    duty_cycle = int((pulse_us / period_us) * 0xFFFF)
    return max(0, min(0xFFFF, duty_cycle))


def set_servo_pulse(pca: PCA9685, channel: int, pulse_us: float) -> None:
    duty = pulse_us_to_duty(pulse_us, SERVO_FREQ_HZ)
    pca.channels[channel].duty_cycle = duty


def main() -> None:
    i2c = busio.I2C(SCL, SDA)
    pca = PCA9685(i2c, address=I2C_ADDRESS)
    pca.frequency = SERVO_FREQ_HZ

    try:
        while True:
            for ch in range(16):
                set_servo_pulse(pca, ch, SERVO_MIN_US)
            time.sleep(SLEEP_SEC)

            for ch in range(16):
                set_servo_pulse(pca, ch, SERVO_MAX_US)
            time.sleep(SLEEP_SEC)
    except KeyboardInterrupt:
        for ch in range(16):
            set_servo_pulse(pca, ch, SERVO_MIN_US)
        pca.deinit()


if __name__ == "__main__":
    main()
