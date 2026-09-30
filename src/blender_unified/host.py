"""Load all four bridges in ONE disposable Blender GUI process.

Run with Blender --factory-startup --python scripts/blender_host.py --
    --config local.json
No addon installation or preference save is performed. All bridges are
included in this package; no external source checkout is required.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import bpy


def load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(path.parent)] if package else None
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--smoke-report", type=Path)
    parser.add_argument("--audit-report", type=Path)
    parser.add_argument("--audit-filter")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if bpy.app.background:
        raise RuntimeError(
            "The assets and authenticated bridges require Blender's GUI event loop; omit -b"
        )
    if hasattr(bpy.types.Scene, "blendermcp_port"):
        raise RuntimeError(
            "Start with --factory-startup; a Blender MCP addon is already registered"
        )
    bpy.context.preferences.use_preferences_save = False
    config = json.loads(args.config.read_text())
    engine = {e["name"]: e for e in config["engines"]}
    bridge_root = Path(__file__).resolve().parent / "bridges"
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    ports = {}
    for name, entry in engine.items():
        argv = entry["args"]
        ports[name] = int(argv[argv.index("--port") + 1])
    if len(set(ports.values())) != len(ports):
        raise RuntimeError("Each bridge needs its own port")
    os.environ["BLENDER_MCP_DISABLE_TELEMETRY"] = "true"
    os.environ["DISABLE_TELEMETRY"] = "true"
    cleanup = []
    try:
        assets = load("unified_assets_addon", bridge_root / "assets.py")
        assets.register()
        cleanup.append(assets.unregister)
        # Runtime preferences are needed by status, consent controls and Premium
        # configuration. They are not installed or saved to user preferences.
        preference_entry = bpy.context.preferences.addons.new()
        preference_entry.module = assets.__name__
        preference_entry.preferences.telemetry_consent = False
        cleanup.append(lambda: bpy.context.preferences.addons.remove(preference_entry))
        assets._blendermcp_unregister_auto_start()
        for scene in bpy.data.scenes:
            scene.blendermcp_auto_start_server = False
            scene.blendermcp_port = ports["assets"]
        assets_bridge = assets.BlenderMCPServer(
            host="127.0.0.1", port=ports["assets"]
        )
        assets_bridge.start()
        if not assets_bridge.running:
            raise RuntimeError("Assets bridge did not start")
        bpy.types.blendermcp_server = assets_bridge
        cleanup.append(assets_bridge.stop)
        bpy.context.scene.blendermcp_server_running = True

        # This fork shares RNA class names with assets. Reuse the common
        # properties and load only its separate authenticated socket server.
        # Its credentials come from BLENDERMCP_* environment variables.
        authenticated = load(
            "unified_authenticated_addon",
            bridge_root / "authenticated/__init__.py",
            package=True,
        )
        for name in ("blendermcp_custom_token", "blendermcp_active_token"):
            setattr(
                bpy.types.Scene,
                name,
                bpy.props.StringProperty(
                    default="", options={"SKIP_SAVE"}, subtype="PASSWORD"
                ),
            )
        for name in (
            "blendermcp_allow_remote_host",
            "blendermcp_restrict_execute_code",
        ):
            setattr(bpy.types.Scene, name, bpy.props.BoolProperty(default=False))
        authenticated_bridge = authenticated.BlenderMCPServer(
            host="127.0.0.1", port=ports["authenticated"]
        )
        authenticated_bridge.start()
        if not authenticated_bridge.running:
            raise RuntimeError("Authenticated bridge did not start")
        cleanup.append(authenticated_bridge.stop)

        modeling = load(
            "unified_modeling_addon",
            bridge_root / "modeling/__init__.py",
            package=True,
        )
        modeling.register()
        cleanup.append(modeling.unregister)
        from unified_modeling_addon import server as blend_server

        blend_server.start_server(host="127.0.0.1", port=ports["modeling"])
        cleanup.append(blend_server.stop_server)

        from blender_unified.bridges.reference import execute_interactive
        from blender_unified.bridges.reference import mcp_to_blender_server as reference

        reference.start("127.0.0.1", ports["reference"])
        cleanup.append(reference.stop)
        bpy.app.timers.register(
            execute_interactive.run, first_interval=0.01, persistent=True
        )
        bpy.app.driver_namespace["blender_unified_cleanup"] = cleanup
        print("BLENDER_UNIFIED_READY", json.dumps(ports), flush=True)
    except Exception:
        for stop in reversed(cleanup):
            try:
                stop()
            except Exception:
                pass
        raise

    if args.smoke_report or args.audit_report:
        script = "audit.py" if args.audit_report else "smoke.py"
        report = args.audit_report or args.smoke_report
        extra_args = ["--filter", args.audit_filter] if args.audit_filter else []
        smoke = subprocess.Popen(
            [
                engine["modeling"]["command"],
                str(Path(__file__).with_name(script)),
                "--config",
                str(args.config.resolve()),
                "--report",
                str(report.resolve()),
                *extra_args,
            ]
        )
        started = time.monotonic()

        def finish():
            if smoke.poll() is None and time.monotonic() - started < (
                1800 if args.audit_report else 120
            ):
                return 0.25
            if smoke.poll() is None:
                smoke.terminate()
            for stop in reversed(cleanup):
                try:
                    stop()
                except Exception:
                    pass
            bpy.ops.wm.quit_blender()
            return None

        bpy.app.timers.register(finish, first_interval=1.0, persistent=True)


if __name__ == "__main__":
    main()
