from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Mapping, Optional

LOG = logging.getLogger(__name__)


class ServoBoard(ABC):
    """Abstract interface for servo boards."""

    @abstractmethod
    def set_pwm_frequency(self, frequency: int) -> None:
        ...

    @abstractmethod
    def send_absolute(self, commands: Mapping[int, int]) -> None:
        """Send absolute PWM commands indexed by 1-based servo IDs."""

    @abstractmethod
    def stop(self) -> None:
        ...


class MockBoard(ServoBoard):
    """Debug helper that just logs outgoing commands."""

    def __init__(self) -> None:
        self.frequency = 50
        self.last_commands: Dict[int, int] = {}

    def set_pwm_frequency(self, frequency: int) -> None:
        self.frequency = frequency
        LOG.info("MockBoard frequency set to %d Hz", frequency)

    def send_absolute(self, commands: Mapping[int, int]) -> None:
        self.last_commands = dict(commands)
        human = ", ".join(f"{idx}:{val}" for idx, val in sorted(commands.items()))
        LOG.debug("[MockBoard] %s", human)

    def stop(self) -> None:
        LOG.info("MockBoard stop requested")
        self.last_commands.clear()


class PCA9685Board(ServoBoard):
    """Minimal PCA9685 driver using smbus2."""

    _MODE1 = 0x00
    _MODE2 = 0x01
    _PRE_SCALE = 0xFE
    _LED0_ON_L = 0x06
    _ALL_LED_ON_L = 0xFA
    _ALL_LED_OFF_L = 0xFC

    def __init__(self, bus: int = 1, address: int = 0x40, frequency: int = 50) -> None:
        try:
            from smbus2 import SMBus  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "smbus2 is required for the PCA9685 backend. "
                "Install with `pip install smbus2`."
            ) from exc

        self._bus = SMBus(bus)
        self._address = address
        self._frequency = frequency
        self._initialize_chip()
        self.set_pwm_frequency(frequency)

    def _initialize_chip(self) -> None:
        self._write_byte(self._MODE2, 0x04)  # Totem pole
        self._write_byte(self._MODE1, 0x00)

    def _write_byte(self, register: int, value: int) -> None:
        self._bus.write_byte_data(self._address, register, value)

    def _read_byte(self, register: int) -> int:
        return self._bus.read_byte_data(self._address, register)

    def set_pwm_frequency(self, frequency: int) -> None:
        frequency = int(frequency)
        prescaleval = 25_000_000.0
        prescaleval /= 4096.0
        prescaleval /= frequency
        prescaleval -= 1.0
        prescale = int(prescaleval + 0.5)

        oldmode = self._read_byte(self._MODE1)
        newmode = (oldmode & 0x7F) | 0x10  # sleep
        self._write_byte(self._MODE1, newmode)
        self._write_byte(self._PRE_SCALE, prescale)
        self._write_byte(self._MODE1, oldmode)
        time.sleep(0.005)
        self._write_byte(self._MODE1, oldmode | 0x80)
        self._frequency = frequency
        LOG.info("PCA9685 PWM frequency set to %d Hz", frequency)

    def send_absolute(self, commands: Mapping[int, int]) -> None:
        for servo, value in commands.items():
            channel = int(servo) - 1
            if channel < 0 or channel > 15:
                raise ValueError(f"Servo index {servo} out of range for PCA9685")
            if value < 0:
                value = 0
            elif value > 4095:
                value = 4095
            base = self._LED0_ON_L + 4 * channel
            self._write_byte(base, 0)
            self._write_byte(base + 1, 0)
            self._write_byte(base + 2, value & 0xFF)
            self._write_byte(base + 3, value >> 8)

    def stop(self) -> None:
        self._write_byte(self._ALL_LED_ON_L, 0)
        self._write_byte(self._ALL_LED_ON_L + 1, 0)
        self._write_byte(self._ALL_LED_OFF_L, 0)
        self._write_byte(self._ALL_LED_OFF_L + 1, 0)
        self._bus.close()
        LOG.info("PCA9685 outputs disabled")


def create_board(
    backend: str,
    *,
    bus: int = 1,
    address: int = 0x40,
    pwm_frequency: int = 50,
) -> ServoBoard:
    backend = backend.lower()
    if backend == "mock":
        board = MockBoard()
        board.set_pwm_frequency(pwm_frequency)
        return board
    if backend in {"pca9685", "pca"}:
        return PCA9685Board(bus=bus, address=address, frequency=pwm_frequency)
    raise ValueError(f"Unsupported hardware backend '{backend}'")
