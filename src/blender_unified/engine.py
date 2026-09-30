"""Run an integrated capability engine in an isolated process."""

import argparse
import importlib
import os
import sys

ENGINE_MODULES = {
    "modeling": "blender_unified.engines.modeling.server",
    "assets": "blender_unified.engines.assets.server",
    "authenticated": "blender_unified.engines.authenticated.server",
    "reference": "blender_unified.engines.reference",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True, choices=ENGINE_MODULES)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    os.environ.update(
        {
            "BLENDER_HOST": "127.0.0.1",
            "BLENDER_PORT": str(args.port),
            "BLENDER_MCP_HOST": "127.0.0.1",
            "BLENDER_MCP_PORT": str(args.port),
            "BLENDER_MCP_DISABLE_TELEMETRY": "true",
            "DISABLE_TELEMETRY": "true",
            "MCP_DISABLE_TELEMETRY": "true",
        }
    )
    sys.argv = [sys.argv[0]]
    server = importlib.import_module(ENGINE_MODULES[args.kind])
    if args.kind == "modeling":
        from .engines.modeling.connection import BlenderConnection

        server._connection = BlenderConnection(host="127.0.0.1", port=args.port)
    server.main()


if __name__ == "__main__":
    main()
