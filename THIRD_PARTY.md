# Upstream attribution

This package incorporates runtime code from the projects below. Server imports were refactored into `blender_unified.engines.*`; Blender bridges live in `blender_unified.bridges.*`. Original copyright and license headers are retained. The generated `names.json` and `inventory.json` record their interfaces; inventory descriptions and schemas originate from these projects.

| Project | Source | License text |
| --- | --- | --- |
| MCP for Blender, Siddharth Ahuja and contributors | https://github.com/ahujasid/mcp-for-blender | [MIT](licenses/community.txt) |
| Blender-MCP security fork, soozs1 and original contributors | https://github.com/soozs1/Blender-MCP | [MIT](licenses/secure.txt) |
| Blend AI contributors | https://github.com/HoldMyBeer-gg/blend-ai | [AGPL-3.0](licenses/blend-ai.txt) |
| Blender MCP, Blender Authors | https://projects.blender.org/lab/blender_mcp | [GPL-3.0](licenses/blender-lab.txt) |

The exact revisions are in `licenses/sources.json` and the packaged `provenance.json`. The latter records original source paths and SHA-256 hashes for imported files, plus a list of integration changes. The independent repositories are not needed at runtime.

The included [Blender Manual](https://docs.blender.org/manual/en/dev/) is by the [Blender Documentation Team](https://projects.blender.org/blender/documentation), licensed under [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) or later except where otherwise noted. Its text is unchanged. The original notice is retained at `engines/reference/data/manual/copyright.rst`; API examples and other documentation retain their embedded notices. These documentation terms are separate from the gateway's AGPL license.

Integration changes: Python import namespaces and enum-module discovery were updated; secure egress imports became relative; the community addon manager resolves the single packaged bridge copy; disabled telemetry configuration and a guard against creating tracking IDs were added. Repository histories, upstream tests, standalone chat clients, caches, and duplicate addon copies are not included.

Blender 5.2 compatibility fixes update animation slots, physics baking contexts, curve handles, annotation capabilities, material copies, boolean slicing, knife projection, recent-file lookup, export format selection, geometry nodes, and render engine validation. The secure Poly Haven category tool now refreshes integration status before checking it. These local changes are recorded in `provenance.json`.

The destination repository originally contained an Apache-2.0 license. Its text is preserved at `licenses/repository-initial-apache.txt`; it does not replace the licenses of this integrated package or its incorporated components.
