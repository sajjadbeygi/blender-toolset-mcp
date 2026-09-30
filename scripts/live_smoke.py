"""Run the packaged live smoke client."""

import runpy

if __name__ == "__main__":
    runpy.run_module("blender_unified.smoke", run_name="__main__")
