"""All real included engines must preserve the pinned upstream interfaces."""

import json
from pathlib import Path

from blender_unified.config import Config
from blender_unified.gateway import Gateway
from blender_unified.settings import write_config


async def test_every_original_tool_and_schema_survives_integration(tmp_path):
    path = tmp_path / "config.json"
    write_config(path, 21876)
    config = Config.load(path)
    assert all("--source" not in e.args for e in config.engines)
    reference = json.loads((Path(__file__).parents[1] / "inventory.json").read_text())
    expected = {
        (variant["engine"], variant["upstream_tool"]): variant
        for tool in reference["tools"]
        for variant in tool["implementations"]
    }
    async with Gateway(config).connect() as gateway:
        actual = {
            (variant["engine"], variant["upstream_tool"]): variant
            for tool in gateway.catalog.inventory()
            for variant in tool["implementations"]
        }
        assert actual.keys() == expected.keys()
        assert len(actual) == 270
        assert len(gateway.catalog.actions) == 243
        for key, variant in actual.items():
            assert variant["inputSchema"] == expected[key]["inputSchema"], key
            assert variant["outputSchema"] == expected[key]["outputSchema"], key


def test_bridge_lookup_resolves_inside_installed_package():
    import blender_unified
    from blender_unified.engines.community.addon_manager import get_bundled_addon_path

    root = Path(blender_unified.__file__).parent
    assert get_bundled_addon_path() == root / "bridges/community.py"
    assert get_bundled_addon_path().is_file()
    assert (root / "engines/lab/data/manual/copyright.rst").is_file()
    assert not (root / "engines/community/bundled").exists()
