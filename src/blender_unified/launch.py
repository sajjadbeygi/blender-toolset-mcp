"""Launch a fresh Blender process with the packaged bridges."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--blender",
        default=shutil.which("blender")
        or "/Applications/Blender.app/Contents/MacOS/Blender",
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--smoke-report", type=Path)
    parser.add_argument("--audit-report", type=Path)
    parser.add_argument("--audit-filter")
    args = parser.parse_args()
    command = [
        args.blender,
        "--factory-startup",
        "--python",
        str(Path(__file__).with_name("host.py")),
        "--",
        "--config",
        str(args.config.resolve()),
    ]
    if args.smoke_report:
        command += ["--smoke-report", str(args.smoke_report.resolve())]
    if args.audit_report:
        command += ["--audit-report", str(args.audit_report.resolve())]
    if args.audit_filter:
        command += ["--audit-filter", args.audit_filter]
    returncode = subprocess.call(command)
    if args.audit_report and not returncode:
        if not args.audit_report.exists():
            returncode = 1
        else:
            report = json.loads(args.audit_report.read_text())
            if (
                not report.get("completed")
                or report["counts"].get("failed", 0)
                or any(r["status"] == "failed" for r in report["system_tools"])
            ):
                returncode = 1
    sys.exit(returncode)


if __name__ == "__main__":
    main()
