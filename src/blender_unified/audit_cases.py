"""Small, explicit fixtures and positive-path cases for every local tool.

Fixtures run only in a factory-startup audit host. External integrations are
reported separately and never silently counted as successful live tests.
"""

BASE = """
import bpy, math, os
from mathutils import Vector
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for other in list(bpy.data.scenes):
    if other != scene: bpy.data.scenes.remove(other)
scene.name = 'Scene'
scene.frame_start = 1
scene.frame_end = 2
scene.frame_set(1)
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
for group in ('materials', 'curves', 'armatures', 'node_groups', 'meshes'):
    for data in list(getattr(bpy.data, group)):
        if data.users == 0: getattr(bpy.data, group).remove(data)
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.object
obj.name = 'AuditMesh'
obj.data.name = 'AuditMeshData'
bpy.ops.mesh.primitive_cube_add(location=(0.7, 0, 0))
bpy.context.object.name = 'AuditTarget'
bpy.ops.curve.primitive_bezier_curve_add(location=(0, 0, 3))
curve = bpy.context.object
curve.name = 'AuditCurve'
curve.data.dimensions = '3D'
mat = bpy.data.materials.new('AuditMaterial')
mat.use_nodes = True
obj.data.materials.append(mat)
mat.node_tree.nodes.new('ShaderNodeValToRGB').name = 'AuditRamp'
mat.node_tree.nodes.new('ShaderNodeTexNoise').name = 'AuditNoise'
mat.node_tree.nodes.new('ShaderNodeMath').name = 'AuditMath'
bpy.ops.object.camera_add(location=(5, -7, 5))
cam = bpy.context.object
cam.name = 'AuditCamera'
cam.rotation_euler = (-cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
bpy.ops.object.light_add(type='AREA', location=(2, -3, 4))
bpy.context.object.name = 'AuditLight'
bpy.context.object.data.energy = 100
bpy.ops.object.armature_add()
bpy.context.object.name = 'AuditArmature'
if 'AuditCollection' not in bpy.data.collections:
    scene.collection.children.link(bpy.data.collections.new('AuditCollection'))
if 'AuditImage' not in bpy.data.images:
    img = bpy.data.images.new('AuditImage', width=8, height=8)
    img.generated_color = (0.2, 0.5, 0.8, 1)
    img.filepath_raw = os.path.join(AUDIT_DIR, 'texture.png')
    img.file_format = 'PNG'
    img.save()
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.context.tool_settings.mesh_select_mode = (True, False, False)
scene.world = scene.world or bpy.data.worlds.new('AuditWorld')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'SOLID'
result = {'ready': True, 'blender': bpy.app.version_string}
"""

GEOMETRY = """
g = bpy.data.node_groups.new('AuditGeometry', 'GeometryNodeTree')
g.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
g.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
s = g.interface.new_socket(name='Amount', in_out='INPUT', socket_type='NodeSocketFloat')
s.default_value = 1
ng_in = g.nodes.new('NodeGroupInput'); ng_in.name = 'Group Input'
ng_out = g.nodes.new('NodeGroupOutput'); ng_out.name = 'Group Output'
g.links.new(ng_in.outputs['Geometry'], ng_out.inputs['Geometry'])
mod = obj.modifiers.new('AuditNodes','NODES'); mod.node_group = g
"""
ANIMATION = "obj.keyframe_insert(data_path='location', frame=1)\nobj.location.x = 1\nobj.keyframe_insert(data_path='location', frame=2)\nscene.frame_set(1)\n"
ANNOTATION = """
for a in list(bpy.data.annotations): bpy.data.annotations.remove(a)
a = bpy.data.annotations.new('AuditAnnotation')
l = a.layers.new(name='AuditLayer')
f = l.frames.new(1)
s = f.strokes.new(); s.points.add(2)
s.points[0].co = (0,0,0); s.points[1].co = (1,0,0)
"""
OPEN_LOOPS = """
verts=[(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
edges=[(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4)]
mesh=bpy.data.meshes.new('AuditLoops'); mesh.from_pydata(verts,edges,[]); obj.data=mesh
for v in mesh.vertices: v.select=True
for e in mesh.edges: e.select=True
"""
OPEN_RING = """
mesh=bpy.data.meshes.new('AuditRing')
verts=[(math.cos(i*math.pi/4),math.sin(i*math.pi/4),0) for i in range(8)]
mesh.from_pydata(verts,[(i,(i+1)%8) for i in range(8)],[]); obj.data=mesh
for v in mesh.vertices: v.select=True
for e in mesh.edges: e.select=True
"""
PARTICLES = (
    "bpy.ops.object.particle_system_add()\nobj.particle_systems[-1].settings.count=5\n"
)
RIGID = "bpy.ops.rigidbody.object_add()\nscene.rigidbody_world.point_cache.frame_start=1\nscene.rigidbody_world.point_cache.frame_end=2\n"
SCULPT = "bpy.ops.object.mode_set(mode='SCULPT')\n"

# Explicit meaningful non-default arguments. Remaining required fields come
# from the named fixture entities below and are JSON-Schema validated first.
OVERRIDES = {
    "inset_faces": {"selection": "CURRENT"},
    "create_object": {"type": "CUBE", "name": "CreatedMesh"},
    "create_polygon_prism": {"sides": 6, "name": "CreatedMesh"},
    "create_threaded_shaft": {
        "diameter": 1.0,
        "length": 2.0,
        "pitch": 0.4,
        "segments": 12,
        "name": "CreatedMesh",
    },
    "rename_object": {"old_name": "AuditMesh", "new_name": "RenamedMesh"},
    "join_objects": {"names": ["AuditMesh", "AuditTarget"]},
    "select_objects": {"names": ["AuditMesh", "AuditTarget"]},
    "set_object_visibility": {"visible": False},
    "parent_objects": {"child": "AuditMesh", "parent": "AuditTarget"},
    "convert_object": {"object_name": "AuditCurve", "target": "MESH"},
    "set_location": {"location": [1, 2, 3]},
    "set_rotation": {"rotation": [0.1, 0.2, 0.3]},
    "set_scale": {"scale": [2, 2, 2]},
    "set_origin": {"type": "GEOMETRY"},
    "create_collection": {"name": "CreatedCollection"},
    "move_to_collection": {"object_names": ["AuditMesh"]},
    "set_collection_visibility": {"visible": False},
    "create_scene": {"name": "CreatedScene"},
    "delete_scene": {"scene_name": "DeleteScene"},
    "set_scene_property": {"property": "fps", "value": 30},
    "create_material": {"name": "CreatedMaterial"},
    "create_principled_material": {"name": "CreatedMaterial", "metallic": 0.4},
    "duplicate_material": {"new_name": "CopiedMaterial"},
    "set_material_color": {"color": [0.8, 0.2, 0.1, 1]},
    "set_material_property": {"property": "roughness", "value": 0.3},
    "set_material_blend_mode": {"mode": "BLEND"},
    "add_shader_node": {"node_type": "ShaderNodeTexVoronoi"},
    "connect_shader_nodes": {
        "from_node": "AuditNoise",
        "from_socket": "Fac",
        "to_node": "Principled BSDF",
        "to_socket": "Roughness",
    },
    "disconnect_shader_nodes": {
        "node_name": "Material Output",
        "socket_name": "Surface",
    },
    "remove_shader_node": {"node_name": "AuditNoise"},
    "set_shader_node_input": {
        "node_name": "AuditNoise",
        "socket": "Scale",
        "value": 2.5,
    },
    "set_shader_node_property": {
        "node_name": "AuditNoise",
        "property": "noise_dimensions",
        "value": "4D",
    },
    "add_color_ramp_element": {
        "node_name": "AuditRamp",
        "position": 0.5,
        "color": [1, 0, 0, 1],
    },
    "remove_color_ramp_element": {"node_name": "AuditRamp", "index": 0},
    "set_color_ramp_element": {
        "node_name": "AuditRamp",
        "index": 0,
        "color": [1, 0, 0, 1],
    },
    "set_color_ramp_interpolation": {
        "node_name": "AuditRamp",
        "interpolation": "CONSTANT",
    },
    "get_color_ramp": {"node_name": "AuditRamp"},
    "create_procedural_material": {"name": "CreatedMaterial", "pattern": "noise"},
    "create_raster_texture": {
        "name": "CreatedTexture",
        "pattern": "runes",
        "size": 64,
        "count": 2,
    },
    "create_light": {"type": "POINT", "name": "CreatedLight"},
    "delete_light": {"object_name": "AuditLight"},
    "set_light_property": {
        "object_name": "AuditLight",
        "property": "energy",
        "value": 250,
    },
    "set_shadow_settings": {"object_name": "AuditLight"},
    "set_world_background": {"color": [0.2, 0.3, 0.4]},
    "create_light_rig": {"type": "THREE_POINT", "target": "AuditMesh"},
    "create_camera": {"name": "CreatedCamera", "location": [0, -5, 2]},
    "set_active_camera": {"object_name": "AuditCamera"},
    "point_camera_at": {"camera_name": "AuditCamera", "target": "AuditMesh"},
    "set_camera_property": {
        "object_name": "AuditCamera",
        "property": "lens",
        "value": 35,
    },
    "capture_viewport": {"width": 64, "height": 64},
    "set_render_engine": {"engine": "BLENDER_WORKBENCH"},
    "set_render_resolution": {"width": 128, "height": 96},
    "set_render_samples": {"samples": 4},
    "set_output_format": {"format": "PNG"},
    "set_eevee_light_path": {"direct_intensity": 0.5},
    "insert_keyframe": {"data_path": "location", "frame": 1, "value": [1, 2, 3]},
    "delete_keyframe": {"data_path": "location", "frame": 1},
    "set_interpolation": {"data_path": "location", "interpolation": "LINEAR"},
    "set_frame": {"frame": 2},
    "set_frame_range": {"start": 1, "end": 3},
    "create_animation_path": {"path_object": "AuditCurve"},
    "create_armature": {"name": "CreatedArmature"},
    "add_bone": {"bone_name": "AddedBone", "head": [0, 0, 1], "tail": [0, 0, 2]},
    "set_bone_property": {"property": "use_deform", "value": False},
    "set_pose": {"location": [0, 0, 0.5]},
    "add_constraint": {
        "constraint_type": "COPY_LOCATION",
        "properties": {"target": "AuditTarget"},
    },
    "parent_mesh_to_armature": {"type": "ARMATURE_NAME"},
    "add_modifier": {"modifier_type": "BEVEL", "name": "AddedModifier"},
    "set_modifier_property": {"property": "width", "value": 0.2},
    "separate_mesh": {"type": "LOOSE"},
    "boolean_operation": {"target_name": "AuditTarget"},
    "decimate_mesh": {"ratio": 0.5},
    "set_edge_crease": {"value": 0.5},
    "spin_mesh": {"steps": 4, "angle": 1.57},
    "select_by_index": {"element": "FACE", "indices": [0]},
    "select_similar": {"type": "FACE_SIDES"},
    "create_curve": {"name": "CreatedCurve", "type": "BEZIER"},
    "set_curve_property": {"property": "bevel_depth", "value": 0.1},
    "create_text": {"text": "Audit", "name": "CreatedText"},
    "create_geometry_nodes": {"name": "CreatedNodes"},
    "add_geometry_node": {
        "modifier_name": "AuditNodes",
        "node_type": "GeometryNodeMeshCube",
    },
    "connect_geometry_nodes": {
        "modifier_name": "AuditNodes",
        "from_node": "Group Input",
        "from_socket": 0,
        "to_node": "Group Output",
        "to_socket": 0,
    },
    "set_geometry_node_input": {
        "modifier_name": "AuditNodes",
        "input_name": "Amount",
        "value": 2.0,
    },
    "list_geometry_node_inputs": {"modifier_name": "AuditNodes"},
    "set_uv_projection": {"projection": "CUBE"},
    "remesh": {"voxel_size": 0.5},
    "add_multires_modifier": {"levels": 1},
    "set_sculpt_brush": {"brush_type": "DRAW"},
    "set_brush_property": {"property": "strength", "value": 0.4},
    "add_particle_system": {"count": 5, "lifetime": 2},
    "add_fluid_sim": {"type": "EFFECTOR"},
    "set_physics_property": {
        "physics_type": "RIGID_BODY",
        "property": "mass",
        "value": 2.0,
    },
    "bake_physics": {"physics_type": "RIGID_BODY"},
    "set_particle_rendering": {
        "render_type": "OBJECT",
        "instance_object": "AuditTarget",
    },
    "create_annotation": {"name": "CreatedAnnotation"},
    "add_annotation_layer": {"layer_name": "AddedLayer"},
    "add_annotation_stroke": {"points": [[0, 0, 0], [1, 1, 0]]},
    "set_annotation_stroke_property": {
        "stroke_index": 0,
        "property": "display_mode",
        "value": "3DSPACE",
    },
    "set_viewport_shading": {"mode": "WIREFRAME"},
    "set_viewport_overlay": {"overlay": "show_floor", "enabled": False},
    "get_viewport_screenshot": {"max_size": 128},
    "sweep_profile_along_path": {
        "path_points": [[0, 0, 0], [0, 0, 2], [1, 0, 3]],
        "radius": 0.1,
        "sides": 8,
        "name": "CreatedSweep",
    },
    "analyze_sweep_path": {
        "path_points": [[0, 0, 0], [0, 0, 2], [1, 0, 3]],
        "radius": 0.1,
    },
}

COMMON = {
    "object_name": "AuditMesh",
    "target_name": "AuditTarget",
    "cutter_name": "AuditCutter",
    "material_name": "AuditMaterial",
    "curve_name": "AuditCurve",
    "armature_name": "AuditArmature",
    "mesh_name": "AuditMesh",
    "bone_name": "Bone",
    "modifier_name": "TestModifier",
    "collection_name": "AuditCollection",
    "annotation_name": "AuditAnnotation",
    "layer_name": "AuditLayer",
    "user_prompt": "Audit tools on a disposable test scene.",
}

EXTRA = {
    "apply_modifier": "obj.modifiers.new('TestModifier','BEVEL')\n",
    "remove_modifier": "obj.modifiers.new('TestModifier','BEVEL')\n",
    "set_modifier_property": "obj.modifiers.new('TestModifier','BEVEL')\n",
    "delete_scene": "bpy.data.scenes.new('DeleteScene')\n",
    "clear_animation": ANIMATION,
    "delete_keyframe": ANIMATION,
    "set_interpolation": ANIMATION,
    "list_keyframes": ANIMATION,
    "inset_faces": "bpy.context.tool_settings.mesh_select_mode=(False,False,True)\nfor p in obj.data.polygons: p.select=(p.index==0)\n",
    "add_geometry_node": GEOMETRY,
    "connect_geometry_nodes": GEOMETRY,
    "set_geometry_node_input": GEOMETRY,
    "list_geometry_node_inputs": GEOMETRY,
    "add_annotation_layer": ANNOTATION,
    "remove_annotation_layer": ANNOTATION,
    "add_annotation_stroke": ANNOTATION,
    "set_annotation_stroke_property": ANNOTATION,
    "bridge_edge_loops": OPEN_LOOPS,
    "fill_faces": OPEN_RING,
    "grid_fill": OPEN_RING,
    "select_similar": "bpy.ops.object.mode_set(mode='EDIT')\nbpy.ops.mesh.select_mode(type='FACE')\nbpy.ops.mesh.select_all(action='SELECT')\nbpy.ops.object.mode_set(mode='OBJECT')\n",
    "set_particle_velocity": PARTICLES,
    "set_particle_rendering": PARTICLES,
    "delete_particle_system": PARTICLES,
    "set_physics_property": RIGID,
    "bake_physics": RIGID,
    "exit_sculpt_mode": SCULPT,
    "set_sculpt_brush": SCULPT,
    "set_brush_property": SCULPT,
    "set_sculpt_symmetry": SCULPT,
    "tris_to_quads": "bpy.ops.object.mode_set(mode='EDIT')\nbpy.ops.mesh.select_all(action='SELECT')\nbpy.ops.mesh.quads_convert_to_tris()\nbpy.ops.object.mode_set(mode='OBJECT')\n",
    "knife_project": "bpy.ops.mesh.primitive_circle_add(vertices=8,radius=0.5,location=(0,0,2))\nbpy.context.object.name='AuditCutter'\nbpy.context.view_layer.objects.active=obj\n",
}

# Postconditions use Blender state, not the handler's own success flag.
CHECKS = {
    "create_object": "'CreatedMesh' in bpy.data.objects",
    "create_polygon_prism": "len(bpy.data.objects['CreatedMesh'].data.vertices) == 12",
    "create_threaded_shaft": "len(bpy.data.objects['CreatedMesh'].data.vertices) > 24",
    "delete_object": "'AuditMesh' not in bpy.data.objects",
    "duplicate_object": "len([o for o in bpy.data.objects if o.name.startswith('AuditMesh')]) == 2",
    "rename_object": "'RenamedMesh' in bpy.data.objects and 'AuditMesh' not in bpy.data.objects",
    "set_location": "tuple(bpy.data.objects['AuditMesh'].location) == (1,2,3)",
    "set_scale": "tuple(bpy.data.objects['AuditMesh'].scale) == (2,2,2)",
    "set_rotation": "abs(bpy.data.objects['AuditMesh'].rotation_euler.x-0.1)<1e-5",
    "parent_objects": "bpy.data.objects['AuditMesh'].parent == bpy.data.objects['AuditTarget']",
    "set_object_visibility": "bpy.data.objects['AuditMesh'].hide_viewport",
    "set_frame": "bpy.context.scene.frame_current == 2",
    "set_frame_range": "bpy.context.scene.frame_end == 3",
    "set_scene_property": "bpy.context.scene.render.fps == 30",
    "create_scene": "'CreatedScene' in bpy.data.scenes",
    "delete_scene": "'DeleteScene' not in bpy.data.scenes",
    "create_collection": "'CreatedCollection' in bpy.data.collections",
    "delete_collection": "'AuditCollection' not in bpy.data.collections",
    "move_to_collection": "bpy.data.objects['AuditMesh'].name in bpy.data.collections['AuditCollection'].objects",
    "create_material": "'CreatedMaterial' in bpy.data.materials",
    "create_principled_material": "'CreatedMaterial' in bpy.data.materials",
    "delete_material": "'AuditMaterial' not in bpy.data.materials",
    "duplicate_material": "'CopiedMaterial' in bpy.data.materials and bpy.data.materials['CopiedMaterial'].node_tree != bpy.data.materials['AuditMaterial'].node_tree",
    "set_material_property": "abs(bpy.data.materials['AuditMaterial'].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value-0.3)<1e-5",
    "add_color_ramp_element": "len(bpy.data.materials['AuditMaterial'].node_tree.nodes['AuditRamp'].color_ramp.elements)==3",
    "remove_shader_node": "'AuditNoise' not in bpy.data.materials['AuditMaterial'].node_tree.nodes",
    "add_modifier": "'AddedModifier' in bpy.data.objects['AuditMesh'].modifiers",
    "remove_modifier": "'TestModifier' not in bpy.data.objects['AuditMesh'].modifiers",
    "apply_modifier": "'TestModifier' not in bpy.data.objects['AuditMesh'].modifiers and len(bpy.data.objects['AuditMesh'].data.vertices)>8",
    "set_modifier_property": "abs(bpy.data.objects['AuditMesh'].modifiers['TestModifier'].width-0.2)<1e-5",
    "subdivide_mesh": "len(bpy.data.objects['AuditMesh'].data.vertices)>8",
    "extrude_faces": "len(bpy.data.objects['AuditMesh'].data.vertices)>8",
    "bridge_edge_loops": "len(bpy.data.objects['AuditMesh'].data.polygons)>0",
    "fill_faces": "len(bpy.data.objects['AuditMesh'].data.polygons)>0",
    "grid_fill": "len(bpy.data.objects['AuditMesh'].data.polygons)>0",
    "inset_faces": "len(bpy.data.objects['AuditMesh'].data.polygons)>6",
    "set_light_property": "bpy.data.objects['AuditLight'].data.energy==250",
    "delete_light": "'AuditLight' not in bpy.data.objects",
    "set_camera_property": "bpy.data.objects['AuditCamera'].data.lens==35",
    "create_camera": "'CreatedCamera' in bpy.data.objects",
    "create_armature": "'CreatedArmature' in bpy.data.objects",
    "add_bone": "'AddedBone' in bpy.data.objects['AuditArmature'].data.bones",
    "set_bone_property": "not bpy.data.objects['AuditArmature'].data.bones['Bone'].use_deform",
    "set_pose": "abs(bpy.data.objects['AuditArmature'].pose.bones['Bone'].location.z-0.5)<1e-5",
    "create_geometry_nodes": "'CreatedNodes' in bpy.data.objects['AuditMesh'].modifiers",
    "add_rigid_body": "bpy.data.objects['AuditMesh'].rigid_body is not None",
    "set_physics_property": "bpy.data.objects['AuditMesh'].rigid_body.mass==2",
    "bake_physics": "bpy.context.scene.rigidbody_world.point_cache.is_baked",
    "add_cloth_sim": "any(m.type=='CLOTH' for m in bpy.data.objects['AuditMesh'].modifiers)",
    "add_fluid_sim": "any(m.type=='FLUID' for m in bpy.data.objects['AuditMesh'].modifiers)",
    "add_particle_system": "len(bpy.data.objects['AuditMesh'].particle_systems)==1",
    "delete_particle_system": "len(bpy.data.objects['AuditMesh'].particle_systems)==0",
    "enter_sculpt_mode": "bpy.context.object.mode=='SCULPT'",
    "exit_sculpt_mode": "bpy.context.object.mode=='OBJECT'",
    "enable_dyntopo": "bpy.data.objects['AuditMesh'].use_dynamic_topology_sculpting",
    "create_annotation": "'CreatedAnnotation' in bpy.data.annotations",
    "add_annotation_layer": "'AddedLayer' in bpy.data.annotations['AuditAnnotation'].layers",
    "remove_annotation_layer": "'AuditLayer' not in bpy.data.annotations['AuditAnnotation'].layers",
    "add_annotation_stroke": "len(bpy.data.annotations['AuditAnnotation'].layers['AuditLayer'].frames[0].strokes)==2",
    "sweep_profile_along_path": "len(bpy.data.objects['CreatedSweep'].data.polygons)>0",
    "set_render_resolution": "bpy.context.scene.render.resolution_x==128",
    "create_curve": "'CreatedCurve' in bpy.data.objects",
    "convert_curve_to_mesh": "bpy.data.objects['AuditCurve'].type=='MESH'",
    "create_text": "bpy.data.objects['CreatedText'].data.body=='Audit'",
    "clear_animation": "bpy.data.objects['AuditMesh'].animation_data is None",
}

CHECKS.update(
    {
        "booltool_auto_slice": "'AuditMesh_slice' in bpy.data.objects and len(bpy.data.objects['AuditMesh_slice'].data.polygons)>0 and len(bpy.data.objects['AuditMesh'].data.polygons)>0",
        "set_render_engine": "bpy.context.scene.render.engine=='BLENDER_WORKBENCH'",
        "set_geometry_node_input": "getattr(bpy.data.objects['AuditMesh'].modifiers['AuditNodes'].properties.inputs, next(s.identifier for s in bpy.data.node_groups['AuditGeometry'].interface.items_tree if s.name=='Amount')).value==2.0",
        "set_interpolation": "all(k.interpolation=='LINEAR' for layer in bpy.data.objects['AuditMesh'].animation_data.action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves for k in fc.keyframe_points)",
    }
)

CHECKS.update(
    {
        "knife_project": "len(bpy.data.objects['AuditMesh'].data.polygons)>6",
        "add_geometry_node": "any(n.bl_idname=='GeometryNodeMeshCube' for n in bpy.data.node_groups['AuditGeometry'].nodes)",
        "add_curve_point": "len(bpy.data.objects['AuditCurve'].data.splines[0].bezier_points)==3",
    }
)

EXTRA["knife_project"] += (
    "\nfrom mathutils import Quaternion\nfor area in bpy.context.screen.areas:\n    if area.type=='VIEW_3D':\n        view=area.spaces.active.region_3d\n        view.view_rotation=Quaternion((1,0,0,0))\n        view.view_location=(0,0,0)\n        view.view_distance=8\n        view.view_perspective='ORTHO'\n"
)
