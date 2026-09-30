"""Run with Blender --background --factory-startup --python this_file."""

import sys
import unittest
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from blender_unified.bridges.modeling.handlers import (
    animation,
    booltool,
    curves,
    file_ops,
    geometry_nodes,
    gpencil,
    materials,
    rendering,
)


class CompatibilityRegression(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add()
        self.obj = bpy.context.object

    def test_layered_action_and_interpolation(self):
        self.obj.keyframe_insert("location", frame=1)
        self.obj.location.x = 2
        self.obj.keyframe_insert("location", frame=5)
        params = {
            "object_name": self.obj.name,
            "data_path": "location[0]",
            "interpolation": "LINEAR",
        }
        self.assertEqual(
            animation.handle_set_interpolation(params)["keyframes_updated"], 2
        )
        keys = animation.handle_list_keyframes(params)
        self.assertEqual(len(keys), 6)
        self.assertEqual([k["value"] for k in keys if k["array_index"] == 0], [0, 2])
        self.assertTrue(
            all(k["interpolation"] == "BEZIER" for k in keys if k["array_index"] != 0)
        )

    def test_geometry_node_creation_and_values(self):
        params = {"object_name": self.obj.name, "name": "Nodes"}
        geometry_nodes.handle_create_geometry_nodes(params)
        mod = self.obj.modifiers["Nodes"]
        mod.node_group.interface.new_socket(
            name="Amount", in_out="INPUT", socket_type="NodeSocketFloat"
        ).default_value = 1
        geometry_nodes.handle_add_geometry_node(
            {"modifier_name": "Nodes", "node_type": "GeometryNodeMeshCube"}
        )
        p = {
            "object_name": self.obj.name,
            "modifier_name": "Nodes",
            "input_name": "Amount",
            "value": 3.5,
        }
        geometry_nodes.handle_set_geometry_node_input(p)
        values = geometry_nodes.handle_list_geometry_node_inputs(p)
        self.assertEqual(next(v["value"] for v in values if v["name"] == "Amount"), 3.5)
        with self.assertRaises(ValueError):
            geometry_nodes.handle_add_geometry_node(
                {"modifier_name": "Nodes", "node_type": "DefinitelyNotANode"}
            )

    def test_material_copy_is_independent(self):
        mat = bpy.data.materials.new("Original")
        mat.use_nodes = True
        materials.handle_duplicate_material(
            {"material_name": mat.name, "new_name": "Copy"}
        )
        copy = bpy.data.materials["Copy"]
        copy.node_tree.nodes.clear()
        self.assertGreater(len(mat.node_tree.nodes), 0)

    def test_curve_operator_enum_maps_to_point_enum(self):
        bpy.ops.curve.primitive_bezier_curve_add()
        obj = bpy.context.object
        before = len(obj.data.splines[0].bezier_points)
        curves.handle_add_curve_point(
            {"curve_name": obj.name, "position": [2, 1, 0], "handle_type": "AUTOMATIC"}
        )
        self.assertEqual(len(obj.data.splines[0].bezier_points), before + 1)
        self.assertEqual(obj.data.splines[0].bezier_points[-1].handle_left_type, "AUTO")

    def test_annotation_points_without_pressure(self):
        ann = bpy.data.annotations.new("Note")
        ann.layers.new("Layer")
        result = gpencil.handle_add_annotation_stroke(
            {
                "annotation_name": "Note",
                "layer_name": "Layer",
                "points": [[0, 0, 0], [1, 0, 0]],
                "pressure": 0.5,
            }
        )
        self.assertEqual(result["point_count"], 2)
        self.assertFalse(result["pressure_supported"])

    def test_slice_produces_two_nonempty_meshes(self):
        obj = self.obj
        bpy.ops.mesh.primitive_cube_add(location=(1, 0, 0))
        target = bpy.context.object
        booltool.handle_booltool_auto_slice(
            {"object_name": obj.name, "target_name": target.name}
        )
        self.assertEqual(len(bpy.data.objects), 2)
        self.assertTrue(all(len(o.data.polygons) > 0 for o in bpy.data.objects))

    def test_render_engine_dynamic_enum(self):
        for engine in ("BLENDER_WORKBENCH", "CYCLES", "BLENDER_EEVEE_NEXT"):
            rendering.handle_set_render_engine({"engine": engine})
            self.assertEqual(
                bpy.context.scene.render.engine,
                "BLENDER_EEVEE" if engine.endswith("_NEXT") else engine,
            )
        with self.assertRaises(ValueError):
            rendering.handle_set_render_engine({"engine": "MISSING_ENGINE"})

    def test_recent_files_and_export_variants(self):
        self.assertIsInstance(file_ops.handle_list_recent_files({}), list)
        self.assertEqual(file_ops._get_extension("scene.glb", "GLTF"), ".glb")
        self.assertEqual(file_ops._get_extension("scene.usdz", "USD"), ".usdz")
        self.assertNotIn(".svg", file_ops.EXPORT_OPERATORS)


result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(CompatibilityRegression)
)
if not result.wasSuccessful():
    raise SystemExit(1)
