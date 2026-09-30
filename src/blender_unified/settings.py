"""Generate settings for the four included capability engines."""

import argparse
import json
import sys
from pathlib import Path

ENGINE_PORTS = {"modeling": 0, "authenticated": 1, "assets": 2, "reference": 3}


def write_config(path: Path, port_base: int = 9876):
    if not 1024 <= port_base <= 65532:
        raise ValueError("Port base must be between 1024 and 65532")
    path = path.resolve()
    runtime = path.parent / ".runtime"
    engines = [
        {
            "name": name,
            "command": sys.executable,
            "args": [
                "-m",
                "blender_unified.engine",
                "--kind",
                name,
                "--port",
                str(port_base + offset),
            ],
            "env": {
                "BLENDERMCP_CACHE_DIR": str(runtime / "tokens"),
                "XDG_CONFIG_HOME": str(runtime / "config"),
            },
            "required": True,
        }
        for name, offset in ENGINE_PORTS.items()
    ]
    path.write_text(
        json.dumps(
            {
                "engines": engines,
                "priority": ["modeling", "authenticated", "reference", "assets"],
                "routes": {},
            },
            indent=2,
        )
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("local.json"))
    parser.add_argument("--port-base", type=int, default=9876)
    args = parser.parse_args()
    write_config(args.output, args.port_base)
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
