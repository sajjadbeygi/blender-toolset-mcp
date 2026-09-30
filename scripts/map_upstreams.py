"""Regenerate canonical tool names from the integrated capability modules."""

import ast
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOURCES = {
    "community": "engines/community",
    "secure": "engines/secure",
    "blend_ai": "engines/modeling/tools",
    "lab": "engines/lab/tools",
}

COMMON = {
    "get_scene_info": "scene.inspect",
    "get_object_info": "object.inspect",
    "get_viewport_screenshot": "viewport.screenshot",
    "execute_blender_code": "code.execute",
    "get_addon_status": "integration.status",
    "disable_telemetry": "privacy.disable_telemetry",
    "record_trajectory_feedback": "feedback.record",
    "describe_node_type": "docs.describe_node",
    "bpy_api_lookup": "docs.lookup_api",
    "set_texture": "assets.polyhaven.set_texture",
    "export_scene": "file.export_scene",
    "generate_hyper3d_model_via_text": "generation.rodin.from_text",
    "generate_hyper3d_model_via_images": "generation.rodin.from_images",
    "poll_rodin_job_status": "generation.rodin.poll",
    "import_generated_asset": "generation.rodin.import",
    "get_hyper3d_status": "generation.rodin.status",
}
LAB = {
    "get_objects_summary": "scene.hierarchy",
    "get_object_detail_summary": "object.summary",
    "get_python_api_docs": "docs.read_api",
    "search_api_docs": "docs.search_api",
    "search_manual_docs": "docs.search_manual",
    "get_screenshot_of_window_as_image": "viewport.window_image",
    "get_screenshot_of_window_as_json": "viewport.window_pixels",
    "get_screenshot_of_area_as_image": "viewport.area_image",
    "render_viewport_to_path": "render.viewport",
    "render_thumbnail_to_path": "render.thumbnail",
    "jump_to_tab_by_name": "workspace.focus_tab",
    "jump_to_tab_by_space_type": "workspace.focus_editor",
    "jump_to_view3d_object_by_name": "viewport.focus_object",
    "jump_to_view3d_object_data_by_name": "viewport.focus_data",
}
DOMAINS = {
    "objects": "object",
    "transforms": "transform",
    "materials": "material",
    "rendering": "render",
    "file_ops": "file",
    "collections": "collection",
    "curves": "curve",
    "geometry_nodes": "geometry",
    "booltool": "boolean",
    "mesh_editing": "mesh",
    "mesh_quality": "mesh",
    "modeling": "mesh",
    "gpencil": "annotation",
    "print3d": "print3d",
}


def action(engine, module, name):
    if name in COMMON:
        return COMMON[name]
    for provider in ("polyhaven", "polypizza", "sketchfab"):
        if provider in name:
            if name.endswith("status"):
                suffix = "status"
            elif "categories" in name:
                suffix = "categories"
            elif "preview" in name:
                suffix = "preview"
            elif name.startswith("search"):
                suffix = "search"
            else:
                suffix = "download"
            return f"assets.{provider}.{suffix}"
    for provider in ("hunyuan", "tripo"):
        if provider in name:
            suffix = (
                "status"
                if name.startswith("get_")
                else "generate"
                if name.startswith("generate_")
                else "poll"
                if name.startswith("poll_")
                else "import"
            )
            return f"generation.{provider}.{suffix}"
    if engine == "lab":
        if name in LAB:
            return LAB[name]
        if name.startswith("get_blendfile_summary_"):
            return "file.inspect_" + name.removeprefix("get_blendfile_summary_")
        if name.endswith("_for_cli") and name.removesuffix("_for_cli") in COMMON:
            return COMMON[name.removesuffix("_for_cli")] + "_cli"
        return "docs." + name
    return DOMAINS.get(module, module) + "." + name


def main():
    names = {}
    for engine, subdirectory in SOURCES.items():
        root = PROJECT / "src/blender_unified"
        names[engine] = {}
        for path in sorted((root / subdirectory).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for dec in node.decorator_list:
                    if (
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "tool"
                    ):
                        registered = next(
                            (
                                k.value.value
                                for k in dec.keywords
                                if k.arg == "name" and isinstance(k.value, ast.Constant)
                            ),
                            node.name,
                        )
                        names[engine][registered] = action(
                            engine, path.stem, registered
                        )
    (PROJECT / "src/blender_unified/names.json").write_text(
        json.dumps(names, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
