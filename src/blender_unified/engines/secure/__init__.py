"""Blender integration through the Model Context Protocol."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("blender-mcp")
except PackageNotFoundError:
    __version__ = "unknown"

from .server import BlenderConnection, get_blender_connection
