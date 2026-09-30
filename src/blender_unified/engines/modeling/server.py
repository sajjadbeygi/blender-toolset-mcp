"""MCP Server entry point for Blender Toolset Modeling."""

from mcp.server.fastmcp import FastMCP

from blender_unified.engines.modeling.connection import BlenderConnection

# Create the MCP server
mcp = FastMCP(
    "Blender Toolset Modeling",
    instructions="The most intuitive and efficient MCP Server for Blender",
)

# Global connection instance
_connection: BlenderConnection | None = None


def get_connection() -> BlenderConnection:
    """Get or create the global Blender connection."""
    global _connection
    if _connection is None:
        _connection = BlenderConnection()
    return _connection


# Import all tool modules to register them with the MCP server
from blender_unified.engines.modeling.tools import (  # noqa: E402, F401
    scene,
    objects,
    transforms,
    modeling,
    materials,
    lighting,
    camera,
    animation,
    rendering,
    curves,
    sculpting,
    uv,
    physics,
    geometry_nodes,
    armature,
    collections,
    file_ops,
    viewport,
    code_exec,
    screenshot,
    selection,
    booltool,
    mesh_editing,
    mesh_quality,
    gpencil,
    sweep,
    print3d,
)

# Import resources and prompts
from blender_unified.engines.modeling.resources import scene_info  # noqa: E402, F401
from blender_unified.engines.modeling.prompts import workflows  # noqa: E402, F401


from blender_unified.engines.modeling.strict import forbid_unknown_parameters  # noqa: E402
from blender_unified.engines.modeling.enum_hints import attach_enum_hints  # noqa: E402
from blender_unified.engines.modeling.aliases import attach_legacy_aliases  # noqa: E402

forbid_unknown_parameters(mcp)
attach_enum_hints(mcp)
attach_legacy_aliases(mcp)


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
