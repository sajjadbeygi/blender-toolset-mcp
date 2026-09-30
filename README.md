# Blender Toolset MCP

**Control Blender through one self-contained Model Context Protocol server.** Create and edit geometry, build materials, animate objects, configure physics, render images, inspect scenes, search Blender documentation, and work with asset services from an MCP-compatible client.

The Python distribution and executable are named **`blender-unified`**. All implementation modules, Blender bridges, and searchable documentation ship in this repository and its wheel.

- **243 distinct Blender tools**, organized by task.
- **3 discovery tools** for finding operations and reading their exact schemas.
- **270 implementation routes**, including alternatives for overlapping operations.
- One public **stdio MCP endpoint** controlling a shared Blender scene.
- Local scene operations work without provider accounts. External asset and generation services have their own requirements.

[Installation](#installation) · [Client setup](#connect-your-mcp-client) · [Capabilities](#capabilities) · [Examples](#example-workflow) · [Configuration](#configuration) · [Testing](#testing-and-verification) · [Troubleshooting](#troubleshooting)

## Requirements

| Requirement | Details |
| --- | --- |
| Python | 3.11 or newer |
| Blender | A GUI installation; live verification used **Blender 5.2.2 LTS on macOS** |
| Package manager | `uv` recommended; installing a built wheel with `pip` is also supported |
| MCP client | A client capable of launching a local stdio MCP server |
| Network | Needed for initial dependency installation and external asset/generation services |

Other operating systems and Blender versions have not received the same live audit. The combined host requires Blender's GUI event loop; do not launch it in background mode. Individual background inspection tools start separate Blender processes when needed.

## Installation

### 1. Get the project

```sh
git clone https://github.com/sajjadbeygi/blender-toolset-mcp.git
cd blender-toolset-mcp
uv sync
```

### 2. Generate a local configuration

```sh
uv run blender-unified-configure --output local.json
```

This creates the settings for the MCP server and its Blender host. It records the Python interpreter's absolute path. Regenerate it if you move the checkout or replace the environment; preserve custom settings before regenerating.

### 3. Start Blender

```sh
uv run blender-unified-host --config local.json
```

The launcher finds `blender` on PATH or uses the standard macOS application path. To choose an executable explicitly:

```sh
uv run blender-unified-host --config local.json --blender /path/to/blender
```

The launcher opens a **new factory-startup Blender window**, registers the packaged bridges for that session, and prints `BLENDER_UNIFIED_READY` when they are ready. It does not install persistent addons or save Blender preferences. Close this window to stop the bridges.

Open your project in that window after startup, or use the file tools. Save work explicitly before closing Blender.

### Install from a wheel

Build from this checkout:

```sh
uv build
python -m pip install dist/blender_unified-0.3.0-py3-none-any.whl
blender-unified-configure --output local.json
blender-unified-host --config local.json
```

The installed package includes the code, bridges, documentation corpus, and license notices. A Git checkout is not needed to run the installed wheel. This guide does not assume a PyPI release is available.

## Connect your MCP client

Keep the Blender host running, then configure your client to launch the MCP endpoint. On macOS or Linux, a typical configuration is:

```json
{
  "mcpServers": {
    "blender-unified": {
      "command": "/ABSOLUTE/PATH/blender-toolset-mcp/.venv/bin/blender-unified",
      "args": [
        "--config",
        "/ABSOLUTE/PATH/blender-toolset-mcp/local.json"
      ]
    }
  }
}
```

Use your client's configuration format and real absolute paths. On Windows, the environment's executable is under `.venv/Scripts/`. Restart or reconnect the client after changing settings.

The host and endpoint are separate processes: the host opens Blender; the endpoint exposes MCP over stdin/stdout. Both must read the same configuration. Client configuration is not installed automatically.

### Check the connection

Ask your client to call:

```text
system.status()
scene.inspect()
viewport.screenshot(max_size=800)
```

`system.status` confirms component discovery and tool counts. `scene.inspect` verifies an actual Blender connection, and the screenshot verifies that the intended scene is visible.

## Capabilities

| Area | Operations |
| --- | --- |
| Objects and transforms | Create, inspect, duplicate, delete, position, rotate, scale, parent, and organize objects |
| Mesh modeling | Extrude, bevel, inset, subdivide, merge, project cuts, repair geometry, and perform booleans |
| Materials | Create and assign materials, edit shader nodes, connect sockets, configure textures and color ramps |
| Geometry nodes | Create node groups and modifiers, add nodes, connect sockets, and set inputs |
| Curves and sweeps | Create curves, edit points and handles, and build swept geometry |
| Animation and rigging | Insert and inspect keyframes, set interpolation, work with armatures, bones, poses, and constraints |
| Physics and sculpting | Configure supported simulations, bake caches, select sculpt tools, and modify brush settings |
| Cameras and lighting | Create and configure cameras and lights, and adjust scene illumination |
| Rendering | Set engine, resolution and output options; render images, animations, thumbnails, and viewport captures |
| Files and scenes | Save, open, import, export, inspect file contents, and identify missing resources |
| Viewport and workspace | Capture screenshots, focus objects, and navigate workspaces and editors |
| Documentation | Search bundled API/manual references and inspect Blender API and node definitions |
| Assets | Search and import from Poly Haven, Sketchfab, and Poly Pizza |
| Generated models | Submit, poll, and import supported Rodin, Hunyuan3D, and Tripo jobs |
| Python | Execute Blender Python for operations that need direct API access |

Find the exact operations at runtime instead of guessing parameters:

```text
system.find_tools(query="keyframe")
system.find_tools(query="material")
system.describe_tool(name="object.inspect")
```

The [full inventory](inventory.json) contains all tool names, implementation choices, and input/output schemas. Availability of an operation does not imply that every parameter combination, extension, provider, or Blender version has been verified.

## Example workflow

These are MCP calls to make through your client, rather than shell commands:

```text
object.create_object(type="CUBE", name="Example", location=[0, 0, 1])
transform.set_location(object_name="Example", location=[1, 2, 3])
object.inspect(object_name="Example")
viewport.screenshot(max_size=800)
file.save_file(filepath="/ABSOLUTE/PATH/example.blend")
```

A direct API operation can use the Python tool:

```text
code.execute(
  code="import bpy\nresult = {'objects': len(bpy.data.objects)}",
  implementation="reference"
)
```

Example requests for an assistant:

- “Create a simple studio scene with a cube, a floor, a camera, and area lighting.”
- “Inspect this mesh, find its modifiers, and show me a viewport screenshot.”
- “Add location keyframes and switch their interpolation to linear.”
- “Find a wood texture on Poly Haven and apply it to the selected object.”

For multi-step changes, inspect the current scene first, verify the result, and save explicitly.

## Configuration

The package contains four capability components. They run as isolated workers and connect to bridges in the same Blender process.

| Component identifier | Purpose | Default port |
| --- | --- | ---: |
| `modeling` | Scene editing, modeling, materials, animation, physics, rendering | 9876 |
| `authenticated` | Authenticated socket route and selected asset operations | 9877 |
| `assets` | Provider integrations, generation, API inspection, export, and integration controls | 9878 |
| `reference` | Documentation, detailed inspection, UI navigation, and background execution | 9879 |

All default bridge sockets bind to loopback. Choose another block of four ports when running multiple instances:

```sh
uv run blender-unified-configure --output local.json --port-base 19876
```

The default selection order is `modeling`, `authenticated`, `reference`, then `assets`. An operation with multiple implementations accepts an optional selector:

```text
object.inspect(object_name="Example", implementation="authenticated")
```

To override the default for one operation, edit the generated configuration's `routes` object:

```json
{
  "routes": {
    "object.inspect": "authenticated"
  }
}
```

This is a configuration fragment, not a replacement for the complete generated file. Keep its `engines` and `priority` settings. Invalid routes fail at startup.

Different implementations can have different parameter and return shapes. Use `system.describe_tool` to inspect the selected branch. Calls are serialized across components. The gateway does not retry mutations or automatically switch implementations after a failure; implementation-specific retry behavior may still apply. Inspect the scene after a timeout before repeating a mutation.

### Blender executable for background tools

The background inspection and execution tools use `BLENDER_PATH`, falling back to `blender` on PATH. Set it in the MCP server's environment, for example in a client's `env` configuration:

```json
{
  "env": {
    "BLENDER_PATH": "/Applications/Blender.app/Contents/MacOS/Blender"
  }
}
```

Selecting the host with `--blender` does not set this separate worker environment variable.

### Updating an existing installation

Version 0.3 uses capability-based component identifiers. Regenerate configurations created before 0.3, reapply custom ports/environment settings/routes, and restart both host and endpoint. Update explicit implementation selectors to the identifiers in the table above. Catalog metadata uses `implementation_routes` and `tool_name`.

## External services

| Integration | Requirements and verification limits |
| --- | --- |
| Poly Haven | Enable its integration in the Blender sidebar; public API search, previews, and 1K texture downloads have been exercised |
| Sketchfab | Enable the integration and configure provider credentials; authenticated download paths were not part of the completed live audit |
| Poly Pizza | Enable the integration and provide its API key; account-dependent calls remain unverified |
| Rodin / Hunyuan3D / Tripo | Appropriate provider credentials, account access, and an actual job; costs, quotas, and availability depend on the provider |
| 3D Print Toolbox | Requires the corresponding Blender extension; absent from the audited factory installation |

The asset component exposes integration controls in Blender's sidebar. Some authenticated routes read `BLENDERMCP_*` credential variables from the **Blender process**. Configuration of one route does not automatically configure every alternative route. Check a provider's status tool before calling it, and inspect the tool description for its prerequisites.

No paid generation jobs were submitted during verification. A disabled integration or missing credential is not a successful end-to-end provider test.

## Data, execution, and privacy

- Blender Python executes with the privileges of the Blender process. This package is not a sandbox.
- Security checks differ between components; authentication on one bridge does not protect the others.
- Telemetry collection defaults to disabled, with temporary Blender consent preferences off. The gateway adds no telemetry.
- Feedback persistence requires telemetry consent and is not verified with the default opt-out configuration.
- Runtime state and pairing tokens live under `.runtime/` beside the configuration and are excluded from Git.
- Provider tools contact external services when called. Local modeling and bundled documentation searches do not require provider accounts.
- Generated settings, credentials, virtual environments, caches, and built distributions are excluded from the repository.

## MCP behavior

Images and structured results are preserved. Viewport captures can return native MCP image blocks. The endpoint also exposes resources, templates, and prompts:

| Interface | Naming |
| --- | --- |
| Inventory resource | `blender-unified://inventory` |
| Component resources | `blender-unified://resource/...` |
| Workflow prompts | `workflow.*` |

Tool-time elicitation and progress forwarding are supported. Sampling, resource subscriptions, and dynamic catalog-change notifications are not implemented. Restart after changing the catalog.

## Testing and verification

The recorded [live audit](tool-audit.json) covers 270 implementation routes on Blender 5.2.2 LTS:

| Result | Routes |
| --- | ---: |
| Passed positive-path live calls | 243 |
| Blocked by prerequisites | 27 |
| Failed | 0 |

The three discovery tools also passed. Of the live passes, **86 include independent scene or output-file assertions**; **157 verify valid responses**. The 27 blocked routes comprise 25 credential/job-dependent provider operations, the 3D Print Toolbox operation, and feedback persistence. These counts are implementation routes, not distinct public tools.

The report records its test date and environment. It is evidence for those cases, not a guarantee for every operation mode or future provider API. Blender 5.2 annotation points do not support pressure; the stroke tool reports `pressure_supported: false`.

### Python checks

```sh
uv run pytest -q
uv run ruff check src scripts tests
uv run blender-unified --config local.json --inventory
```

Tests cover real MCP subprocesses, schema preservation, routing, output formats, resource and prompt handling, pagination, elicitation, error detection, and serialized execution.

### Live smoke test

```sh
uv run blender-unified-configure --output smoke-config.json --port-base 20876
uv run blender-unified-host --config smoke-config.json --smoke-report blender-smoke.json
```

This uses a disposable factory scene to exercise all four components, inspect and mutate an object, search documentation, capture a viewport image, read a resource and prompt, and clean up. The window closes automatically.

### Full live audit

```sh
uv run blender-unified-configure --output audit-config.json --port-base 24876
BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender uv run blender-unified-host --config audit-config.json --audit-report tool-audit.json
```

Adjust the executable path for your installation. The audit resets its factory scene between cases, writes fixtures under `.runtime/tool-audit`, downloads public Poly Haven assets, and closes its window. It leaves provider jobs requiring credentials or payment unsubmitted.

For a targeted rerun, use a separate output file:

```sh
uv run blender-unified-host --config audit-config.json --audit-report targeted-audit.json --audit-filter add_geometry_node,list_keyframes
```

Direct Blender regression tests:

```sh
/path/to/blender --background --factory-startup --python-exit-code 1 --python tests/blender_regressions.py
```

Before publishing audit artifacts, remove local paths and other environment-specific information. The checked-in report has machine-specific paths redacted.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Client discovers tools but scene calls fail | Start the Blender host and wait for `BLENDER_UNIFIED_READY`; ensure both processes use the same config |
| Address already in use | Close the previous test host or generate settings with another `--port-base` |
| Blender executable not found | Set `--blender` for the host and `BLENDER_PATH` for background worker tools |
| Configuration fails after moving the project | Regenerate it so its interpreter path is correct |
| Old configuration rejected after upgrading | Regenerate for 0.3 and update component selectors/routes |
| Unknown command or integration disabled | Enable the relevant Blender integration and check its status tool |
| Provider rejects a request | Check credentials, account permissions, quotas, job IDs, and the chosen implementation's schema |
| Viewport operation fails | Use the GUI host and open a 3D Viewport; operators can require a particular mode or selection |
| A call times out | Inspect the current scene before retrying; a mutation may already have happened |
| Only the printability check is unavailable | Install and enable the required 3D Print Toolbox extension |

When reporting a bug, include the package and Blender versions, operating system, canonical tool name, selected implementation, minimal arguments, and relevant error text. Remove credentials and private scene data.

## Repository layout

```text
src/blender_unified/
  server.py, gateway.py, catalog.py   Public MCP endpoint and routing
  engine.py, config.py, settings.py  Component startup and configuration
  host.py, launch.py                Blender host lifecycle
  audit.py, audit_cases.py, smoke.py Live verification
  engines/                          Included capability implementations
    modeling/, assets/, authenticated/, reference/
  bridges/                          Blender-side implementations
  names.json                        Canonical tool-name mapping
  provenance.json                   Source and modification records
scripts/                            Maintenance and compatibility entry points
tests/                              Protocol and Blender regression tests
licenses/                           License texts and source records
inventory.json                      Complete tool schema snapshot
tool-audit.json                     Recorded per-route verification
```

## Development

```sh
uv sync
uv run pytest -q
uv run ruff check src scripts tests
uv build
```

After changing tool definitions, regenerate name mappings with `uv run python scripts/refresh_catalog.py`, inspect the inventory, and run the affected live tests. Keep schemas and recorded inventory consistent. Do not count unavailable provider flows as passing tests.

## License and notices

The package is distributed under [AGPL-3.0-or-later](LICENSE). Incorporated code and documentation retain their applicable licenses and attribution in [THIRD_PARTY.md](THIRD_PARTY.md), [licenses/](licenses/), and the provenance manifest. These records are retained independently of product branding. They do not represent separately installed runtime packages.
