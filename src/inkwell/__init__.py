"""Inkwell - Transform podcast episodes into structured markdown notes."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("inkwell-cli")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
