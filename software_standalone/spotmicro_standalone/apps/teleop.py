from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from ..runtime import SpotMicroTeleop


def _parse_address(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    value = value.strip().lower()
    if value.startswith("0x"):
        return int(value, 16)
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Spot Micro standalone teleop (no ROS required)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to YAML config (defaults to packaged config).",
    )
    parser.add_argument(
        "--backend",
        choices=("mock", "pca9685"),
        help="Hardware backend to use (overrides config).",
    )
    parser.add_argument(
        "--pwm-frequency",
        type=int,
        help="PWM frequency in Hz (overrides config).",
    )
    parser.add_argument(
        "--i2c-bus",
        type=int,
        help="I2C bus index for PCA9685 backend.",
    )
    parser.add_argument(
        "--i2c-address",
        type=str,
        help="I2C address (decimal or hex) for PCA9685 backend.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    app = SpotMicroTeleop(
        config_path=str(args.config) if args.config else None,
        backend=args.backend,
        pwm_frequency=args.pwm_frequency,
        i2c_bus=args.i2c_bus,
        i2c_address=_parse_address(args.i2c_address),
    )
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
