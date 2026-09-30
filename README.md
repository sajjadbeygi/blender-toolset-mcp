# Blender Unified MCP

A self-contained Python package combining four Blender MCP implementations into one public interface: **243 canonical Blender tools**, plus three discovery tools, preserving all **270 original tool registrations**.

All required server code, Blender bridges, and searchable documentation are included. There are no sibling repositories to clone, install, or retain. Overlapping operations share a canonical name; specialized operations retain distinct names. The Blender launcher runs the bridges against **one scene**.

## Install and run

Requires Python 3.11+ and a GUI installation of Blender. Tested with Blender 5.2.2 on macOS.

From this source directory:

```sh
uv sync
uv run blender-unified-configure --output local.json
uv run blender-unified-host --config local.json
```

The host launcher uses `blender` from PATH, or the standard macOS application path. Supply `--blender /path/to/blender` on other installations. It opens a new factory-startup window, registers the included bridges for that session, and does not install addons or save preferences. Wait for `BLENDER_UNIFIED_READY`. Close that window to stop the bridges.

You can also install the built wheel into a Python environment with `pip install dist/blender_unified-0.2.1-py3-none-any.whl`, then use the same `blender-unified-configure` and `blender-unified-host` commands. The wheel includes all engine dependencies as package requirements, all bridge code, the local API/manual corpus, and attribution. Git and source checkouts are not needed.

Do not use Blender's `-b` mode for the combined host: two bridges require the GUI event loop. Default ports are 9876 (modeling), 9877 (secure), 9878 (community), and 9879 (Lab), bound to loopback. To choose different ports:

```sh
uv run blender-unified-configure --output local.json --port-base 19876
```

The host reads the same config as the MCP server. Configuration generation writes the active Python interpreter's absolute path; regenerate it after moving the environment. If using an existing config, preserve any custom routes or environment settings before regenerating.

Configure your MCP client to run:

```json
{
  "mcpServers": {
    "blender-unified": {
      "command": "/ABSOLUTE/PATH/blender-unified/.venv/bin/blender-unified",
      "args": ["--config", "/ABSOLUTE/PATH/blender-unified/local.json"]
    }
  }
}
```

The unified endpoint uses stdio. This example has not been written into any installed client's settings.

## Capabilities

| Integrated engine | Original tools | Main capabilities |
| --- | ---: | --- |
| Modeling, from Blend AI | 186 | Modeling, transforms, animation, materials, nodes, physics, rigging, rendering, files, curves, sculpting, mesh repair, 3D printing |
| Community MCP for Blender | 36 | Asset libraries, Rodin/Hunyuan/Tripo, bpy lookup, node descriptions, export, addon and telemetry controls |
| Blender Lab | 26 | API/manual search, detailed file inspection, UI navigation, screenshots, rendering, background Blender execution |
| Security-focused fork | 22 | Alternate implementations using its authenticated socket and integration request restrictions |

[Full inventory](inventory.json) includes original names, canonical names, schemas, and default implementations. The imported revisions are recorded in [upstreams.lock.json](upstreams.lock.json). Imported file paths and original hashes are recorded in the packaged `provenance.json`.

“Superset” means every original tool has a callable route. It does not mean every operation has been tested end to end, that paid services become free, or that one engine's security controls protect another engine. The implementations still use isolated worker processes and distinct internal bridge protocols. They are modules of this one distribution, not dependencies on separate Blender MCP packages.

## Interface

```text
system.find_tools(query="keyframe")
system.describe_tool(name="object.inspect")
object.create_object(type="CUBE", name="Example", location=[0, 0, 1])
object.inspect(object_name="Example")
transform.set_location(object_name="Example", location=[1, 2, 3])
viewport.screenshot(max_size=800)
docs.search_api(query="bpy.types.Object", max_results=5)
```

Overlapping tools accept an optional `implementation` selector:

```text
object.inspect(object_name="Example", implementation="secure")
code.execute(code="import bpy\nresult = {'objects': len(bpy.data.objects)}", implementation="lab")
```

The default priority is `blend_ai`, `secure`, `lab`, `community`. These identifiers remain stable for existing callers. Override specific tools in the config's `routes`, for example `"object.inspect": "secure"`. Invalid or unavailable routes fail startup.

Parameter and return conventions can differ across implementations. The public JSON Schema describes each branch; `system.describe_tool` returns its original schema and description. Images, structured results, error flags, progress, and tool-time elicitation are preserved. Modeling screenshots are additionally exposed as native MCP image blocks while retaining their structured output.

Resources and resource templates use `blender-unified://resource/...` URIs. The full catalog is available at `blender-unified://inventory`. Prompts use `workflow.*` names and carry source-to-canonical name mappings. Sampling, resource subscriptions, and dynamic list-change notifications are not implemented; restart if a catalog changes.

## Integrations and behavior

Enable external integrations through Blender's community sidebar checkboxes. Provider credentials, subscriptions, Premium eligibility, quotas, and network access remain necessary. The secure bridge reads credentials from its documented `BLENDERMCP_*` environment variables in the **Blender process**; its conflicting preferences panel is not registered. Shared integration toggles and temporary community preferences are available in the combined host.

The gateway adds no telemetry. Included community defaults disable collection and prevent creation of a persistent tracking ID. The host creates temporary preferences with consent off and auto-saving disabled. The secure client's token cache is stored under `.runtime/tokens` beside the config. External asset requests still contact their providers when explicitly used.

Security policies remain engine-specific. Other bridges do not inherit the secure engine's authentication or egress restrictions. Python execution runs with Blender's privileges; this package is not a sandbox.

The gateway serializes operations across engines and does not retry or switch engines after a failure. Existing engine retry behavior is unchanged. A timeout can occur after a mutation; inspect the scene before retrying. `system.status` reports engine discovery, not proof of Blender connectivity or provider availability.

## Package layout

```text
src/blender_unified/
  server.py, gateway.py, catalog.py   unified MCP interface
  engine.py, settings.py, launch.py  worker/config/host entry points
  host.py, smoke.py                  packaged Blender host and live test
  engines/                          integrated server implementations
    modeling/, community/, secure/, lab/
  bridges/                          included Blender-side code
    modeling/, community.py, secure/, lab/
  provenance.json                   origins and original file hashes
```

The community bridge has one copy; addon lookup resolves it inside the package. Server imports and enum discovery use the integrated namespaces. The secure bridge uses a relative egress import. The local documentation corpus accounts for most of the package size. Repository histories, standalone chat clients, upstream test trees, caches, and duplicate addon copies were omitted.

## Verification

```sh
uv run pytest -q
uv run ruff check src scripts tests
uv run blender-unified --config local.json --inventory
```

Tests exercise real stdio MCP subprocesses, routing and schema validation, images and structured results, binary resources, pagination, templates, prompts, elicitation, error handling, and operation serialization. The integration test starts every included engine and compares all 270 input/output schemas with the original inventory.

Run live Blender checks in a disposable factory scene, using unused ports:

```sh
uv run blender-unified-configure --output smoke-config.json --port-base 20876
uv run blender-unified-host --config smoke-config.json --smoke-report blender-smoke.json
```

The smoke test creates an object through the modeling engine, inspects it through all four engines, changes its transform, verifies it through Lab, exercises docs and telemetry opt-out, captures a viewport image, reads a resource and prompt, and deletes the object. The test window closes automatically. [Results](blender-smoke.json) record the checks. Paid generation, asset downloads, and every specialized modeling operation are not covered.

## Full live audit

The [per-tool report](tool-audit.json) covers all **270 implementation routes** on Blender 5.2.2 LTS: **243 passed, 27 blocked, zero failed**, plus all three gateway discovery tools passed. Counts refer to implementation routes, not the 243 distinct public Blender tools. Each available route received a positive-path call through the public MCP endpoint in a disposable scene. The report distinguishes independent Blender/file assertions from response-only checks. It does not establish every parameter combination or compatibility with other Blender versions.

The 27 blocked routes comprise 25 credential/job-dependent provider operations, 3D Print Toolbox (extension absent), and feedback persistence (telemetry consent remains off). Poly Haven category/search/preview, actual 1K texture downloads, and cached-texture application were exercised. No paid generation jobs were submitted.

The audit found and fixed Blender compatibility defects in animation, baking, curves, annotations, materials, boolean slicing, knife projection, recent-file lookup, export format selection, geometry nodes, and rendering, plus a stale secure Poly Haven status check. Eight direct Blender regression tests and 18 Python tests pass. Blender 5.2 annotation points no longer support pressure; the stroke tool reports this explicitly with `pressure_supported: false`.

```sh
uv run blender-unified-configure --output audit-config.json --port-base 24876
BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender uv run blender-unified-host --config audit-config.json --audit-report tool-audit.json
```

Set `BLENDER_PATH` to your Blender executable so Lab's background tools can launch it. Use `--blender` as well if the host executable is elsewhere. The audit resets its own factory scene between cases, writes fixtures under `.runtime/tool-audit`, downloads public Poly Haven assets, and closes its test window. For a targeted rerun use `--audit-filter tool_name,another_tool` with a different report filename to preserve the complete report.

Direct Blender regressions:

```sh
/path/to/blender --background --factory-startup --python-exit-code 1 --python tests/blender_regressions.py
```

## Attribution

New gateway code is AGPL-3.0-or-later. Incorporated components retain their original notices and applicable licenses. The Blender Manual retains its separate CC-BY-SA attribution. See [THIRD_PARTY.md](THIRD_PARTY.md), `licenses/`, and the packaged provenance manifest. Repository: [sajjadbeygi/blender-toolset-mcp](https://github.com/sajjadbeygi/blender-toolset-mcp).
