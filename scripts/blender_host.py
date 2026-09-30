"""Run the packaged Blender host from a source checkout."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from blender_unified.host import main

if __name__ == "__main__":
    main()
