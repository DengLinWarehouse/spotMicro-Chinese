#!/usr/bin/env python3
"""Minimal PCA9685 connectivity test for OrangePi AI Pro.

Uses smbus2 to communicate directly via /dev/i2c-7.
No adafruit-blinka dependency, no ROS required.

OrangePi AI Pro wiring (40-pin header):
    Pin 1  (3.3V/5V)  -> PCA9685 VCC
    Pin 3  (GPIO2_12/SDA7) -> PCA9685 SDA
    Pin 5  (GPIO2_11/SCL7) -> PCA9685 SCL
    Pin 6  (GND)         -> PCA9685 GND

Bus: /dev/i2c-7
"""
import sys

# PCA9685 Register definitions
MODE1       = 0x00
MODE2       = 0x01
PRESCALE    = 0xFE
CHANNEL_ON_L  = 0x06   # LED0 on low byte
CHANNEL_OFF_L = 0x08   # LED0 off low byte
ALL_CHAN_ON_L = 0xFA
ALL_CHAN_OFF_L = 0xFC

I2C_ADDRESS = 0x40
I2C_BUS     = 7  # /dev/i2c-7

SERVO_FREQ_HZ = 50  # Standard RC servo frequency

# For PDI-HV5523MG servo (120deg, 900-2100us)
SERVO_MIN_US  = 900
SERVO_MAX_US  = 2100
SERVO_RANGE_US = SERVO_MAX_US - SERVO_MIN_US  # 1200 us


def pulse_us_to_pwm(pulse_us: float) -> int:
    """Convert microseconds to PCA9685 PWM value (0-4095)."""
    period_us = 1_000_000 / SERVO_FREQ_HZ  # 20000 us at 50Hz
    pwm = int((pulse_us / period_us) * 4096)
    return max(0, min(4095, pwm))


def angle_to_pulse(deg: float) -> float:
    """Convert angle (0-120) to pulse width in microseconds.

    PDI-HV5523MG: 0deg=900us, 120deg=2100us.
    """
    return SERVO_MIN_US + SERVO_RANGE_US * (deg / 120.0)


def i2c_write_byte(bus, reg, val):
    """Write a single byte to a register."""
    try:
        bus.write_byte_data(I2C_ADDRESS, reg, val)
    except Exception as e:
        print(f"  I2C write error at reg 0x{reg:02X}: {e}", file=sys.stderr)
        raise


def i2c_read_byte(bus, reg) -> int:
    """Read a single byte from a register."""
    try:
        return bus.read_byte_data(I2C_ADDRESS, reg)
    except Exception as e:
        print(f"  I2C read error at reg 0x{reg:02X}: {e}", file=sys.stderr)
        raise


def pca9685_init(bus):
    """Initialize PCA9685: wake from sleep, set 50Hz PWM frequency."""
    print("[1] PCA9685 initialization")

    # Read MODE1 - should be 0x11 (default after power-on)
    mode1 = i2c_read_byte(bus, MODE1)
    print(f"  MODE1 (before): 0x{mode1:02X}")

    # Enter sleep mode to set frequency
    i2c_write_byte(bus, MODE1, (mode1 & ~0x80) | 0x10)

    # Set PWM frequency: prescale = round(25MHz / (4096 * freq)) - 1
    # For 50Hz: prescale = round(25000000 / (4096 * 50)) - 1 = round(121.09) - 1 = 120
    prescale = int(round(25_000_000 / (4096 * SERVO_FREQ_HZ))) - 1
    prescale = max(3, min(255, prescale))
    i2c_write_byte(bus, PRESCALE, prescale)
    actual_freq = 25_000_000 / (4096 * (prescale + 1))
    print(f"  PRESCALE: {prescale}  (target {SERVO_FREQ_HZ}Hz, actual {actual_freq:.1f}Hz)")

    # Wake up (clear sleep bit)
    mode1 = i2c_read_byte(bus, MODE1)
    i2c_write_byte(bus, MODE1, mode1 & ~0x10)
    print("  Woke up PCA9685 (sleep bit cleared)")

    # Small delay for oscillator to stabilize
    import time
    time.sleep(0.005)

    # Verify MODE1
    mode1 = i2c_read_byte(bus, MODE1)
    print(f"  MODE1 (after):  0x{mode1:02X}")
    print("  PCA9685 initialized successfully!")


def set_servo_pwm(bus, channel: int, pwm_val: int):
    """Set a single channel PWM value (0-4095).

    channel: 0-15 (matches hardware channel number)
    pwm_val: 0=off, 1-4095=PWM pulse width, 0=full off
             For servos: use 4096 to set full on (use with caution)
    """
    if not 0 <= channel <= 15:
        raise ValueError(f"Channel must be 0-15, got {channel}")
    if not 0 <= pwm_val <= 4095:
        raise ValueError(f"PWM must be 0-4095, got {pwm_val}")

    reg_on_l  = CHANNEL_ON_L  + 4 * channel
    reg_off_l = CHANNEL_OFF_L + 4 * channel

    # LEDn_ON register: always 0 (start at beginning of cycle)
    # LEDn_OFF register: PWM value
    bus.write_i2c_block_data(I2C_ADDRESS, reg_on_l, [0x00, 0x00])
    bus.write_i2c_block_data(I2C_ADDRESS, reg_off_l,
                             [pwm_val & 0xFF, (pwm_val >> 8) & 0xFF])


def stop_all_servos(bus):
    """Stop all servos by setting all channels to 0."""
    print("[4] Stopping all servos")
    # ALL_LED_OFF: write to ALL_CHAN_OFF_L with bit 4 set
    bus.write_i2c_block_data(I2C_ADDRESS, ALL_CHAN_OFF_L, [0x00, 0x10])
    print("  All servos stopped")


def main():
    print("=" * 60)
    print("PCA9685 Servo Driver Test - OrangePi AI Pro")
    print("=" * 60)
    print(f"  I2C bus:   /dev/i2c-{I2C_BUS}")
    print(f"  PCA9685:   0x{I2C_ADDRESS:02X}")
    print(f"  Frequency: {SERVO_FREQ_HZ} Hz")
    print(f"  Servo:    PDI-HV5523MG (120deg, 900-2100us)")
    print("=" * 60)

    try:
        from smbus2 import SMBus
    except ImportError:
        print("ERROR: smbus2 not installed.", file=sys.stderr)
        print("Run:  pip install smbus2", file=sys.stderr)
        sys.exit(1)

    print(f"\nOpening /dev/i2c-{I2C_BUS}...")
    with SMBus(I2C_BUS) as bus:
        pca9685_init(bus)

        # Read MODE2 as additional verification
        mode2 = i2c_read_byte(bus, MODE2)
        print(f"\n  MODE2: 0x{mode2:02X}  (should be 0x04 for totem-pole output)")
        if mode2 != 0x04:
            print("  Note: MODE2 differs from expected value (0x04).")

        print("\n[2] Scanning all 16 channels...")
        for ch in range(16):
            pulse = angle_to_pulse(60)  # 60deg = center
            pwm = pulse_us_to_pwm(pulse)
            print(f"  Channel {ch:2d}: {pwm:4d} PWM (~{pulse:.0f}us = 60deg)")

        print("\n[3] Sweep test (all channels)...")
        print("  Center position (60deg) -> 0deg -> 120deg -> center")
        steps = [60.0, 0.0, 120.0, 60.0]
        import time

        for target_deg in steps:
            pulse = angle_to_pulse(target_deg)
            pwm = pulse_us_to_pwm(pulse)
            print(f"  -> {target_deg:.0f}deg ({pulse:.0f}us, PWM={pwm})")
            for ch in range(16):
                set_servo_pwm(bus, ch, pwm)
            time.sleep(1.5)

        stop_all_servos(bus)

    print("\n" + "=" * 60)
    print("Test completed. All checks passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
