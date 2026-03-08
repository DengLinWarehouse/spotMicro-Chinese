"""
SpotMicro standalone package.

This package refactors the original ROS-centric Spot Micro codebase so it can
run directly on Linux or Windows without ROS. See README in the project root
for usage instructions.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("spotmicro-standalone")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__"]
