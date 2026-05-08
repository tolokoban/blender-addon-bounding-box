bl_info = {
    "name": "BBox",
    "version": (0, 1, 0),
    "author": "Tolokoban",
    "blender": (5, 1, 0),
    "category": "3D View",
}

import bpy
import bmesh
import json
import math
import os
import mathutils

from . import utils
from . import slicing

def create_octree_collection():
    """Remove existing 'Octree' collection and recreate it."""
    scene = bpy.context.scene
    existing = bpy.data.collections.get("Octree")
    if existing:
        for obj in existing.all_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for child in list(existing.children):
            bpy.data.collections.remove(child)
        bpy.data.collections.remove(existing)
    col = bpy.data.collections.new("Octree")
    scene.collection.children.link(col)
    return col

def compute_bbox(obj, force_cube=False):
    bounds = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bounds]
    ys = [v.y for v in bounds]
    zs = [v.z for v in bounds]
    min_v = mathutils.Vector((min(xs), min(ys), min(zs)))
    max_v = mathutils.Vector((max(xs), max(ys), max(zs)))
    if force_cube:
        center = (min_v + max_v) / 2
        half = max(max_v.x - min_v.x, max_v.y - min_v.y, max_v.z - min_v.z) / 2
        min_v = center - mathutils.Vector((half, half, half))
        max_v = center + mathutils.Vector((half, half, half))
    return min_v, max_v

def compute_bbox_from_list(objects):
    bboxes = [compute_bbox(obj) for obj in objects]
    min_v = mathutils.Vector((
        min([v[0].x for v in bboxes]), 
        min([v[0].y for v in bboxes]), 
        min([v[0].z for v in bboxes]), 
    ))
    max_v = mathutils.Vector((
        max([v[1].x for v in bboxes]), 
        max([v[1].y for v in bboxes]), 
        max([v[1].z for v in bboxes]), 
    ))
    # Make if a regular cube
    center = (min_v + max_v) / 2
    half = max(max_v.x - min_v.x, max_v.y - min_v.y, max_v.z - min_v.z) / 2
    min_v = center - mathutils.Vector((half, half, half))
    max_v = center + mathutils.Vector((half, half, half))
    return min_v, max_v

def decimate(obj):
    print("Decimate...")
    mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
    mod.ratio = 0.13
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

class BBOX_OT_copy(bpy.types.Operator):
    bl_idname = "bbox.copy_to_clipboard"
    bl_label = "Copy to clipboard"

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        min_v, max_v = compute_bbox(obj, context.scene.bbox_force_cube)
        data = {"bbox": {"min": list(min_v), "max": list(max_v)}}
        context.window_manager.clipboard = json.dumps(data, indent=4)
        return {'FINISHED'}


class BBOX_OT_show(bpy.types.Operator):
    bl_idname = "bbox.show_bounding_box"
    bl_label = "Show Root Bounding Box"

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        name = obj.name + ".BBox"
        existing = bpy.data.objects.get(name)
        if existing:
            bpy.data.objects.remove(existing, do_unlink=True)
        min_v, max_v = compute_bbox(obj, context.scene.bbox_force_cube)
        center = (min_v + max_v) / 2
        size = max_v - min_v
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(mesh)
        bm.free()
        box = bpy.data.objects.new(name, mesh)
        box.location = center
        box.scale = size
        box.display_type = 'WIRE'
        context.collection.objects.link(box)
        bpy.ops.object.select_all(action='DESELECT')
        box.select_set(True)
        context.view_layer.objects.active = box
        bpy.ops.view3d.view_selected()
        return {'FINISHED'}


class BBOX_OT_split(bpy.types.Operator):
    bl_idname = "bbox.split_bounding_box"
    bl_label = "Show Children Bounding Boxes"

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {'CANCELLED'}
        min_v, max_v = compute_bbox(obj, context.scene.bbox_force_cube)
        half_size = (max_v - min_v) / 2
        suffixes = ("000", "100", "010", "110", "001", "101", "011", "111")
        for suffix in suffixes:
            name = f"{obj.name}.{suffix}"
            existing = bpy.data.objects.get(name)
            if existing:
                bpy.data.objects.remove(existing, do_unlink=True)
        for suffix in suffixes:
            ix, iy, iz = int(suffix[0]), int(suffix[1]), int(suffix[2])
            lo = mathutils.Vector((
                min_v.x + ix * half_size.x,
                min_v.y + iy * half_size.y,
                min_v.z + iz * half_size.z,
            ))
            center = lo + half_size / 2
            name = f"{obj.name}.{suffix}"
            mesh = bpy.data.meshes.new(name)
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            bm.to_mesh(mesh)
            bm.free()
            box = bpy.data.objects.new(name, mesh)
            box.location = center
            box.scale = half_size
            box.display_type = 'WIRE'
            context.collection.objects.link(box)
        return {'FINISHED'}


def generate_decimated_lods(collection, obj, level):
    print(f"Decimating {level} LODs...")
    lods_col = bpy.data.collections.new("LODs")
    collection.children.link(lods_col)
    lods = [utils.clone(obj, "LOD-" + str(level))]
    lods_col.objects.link(lods[0])
    for i in range(level - 1, -1, -1):
        new_obj = utils.clone(lods[-1], "LOD-" + str(i))
        lods_col.objects.link(new_obj)
        decimate(new_obj)
        lods.append(new_obj)
    print("Generated:", ", ".join([obj.name for obj in lods]))
    return lods


class BBOX_OT_copy_report(bpy.types.Operator):
    bl_idname = "bbox.copy_report"
    bl_label = "Copy Report to clipboard"

    def execute(self, context):
        context.window_manager.clipboard = context.scene.bbox_lod_report
        return {'FINISHED'}


class BBOX_OT_lods(bpy.types.Operator):
    bl_idname = "bbox.slice_lods"
    bl_label = "Slice to create LODs"

    def execute(self, context):
        try:
            max_level = context.scene.bbox_max_levels
            if max_level < 1:
                return {'FINISHED'}
            collection = create_octree_collection()
            obj = context.active_object
            wm = context.window_manager
            wm.progress_begin(0, max_level)
            lods = generate_decimated_lods(collection, obj, max_level)
            min_v, max_v = compute_bbox_from_list(lods)
            bbox = [
                [min_v.x, min_v.y, min_v.z],
                [max_v.x, max_v.y, max_v.z]
            ]
            # Create wireframe box matching bbox
            center = (min_v + max_v) / 2
            scale = (max_v - min_v) / 2
            voxels_col = bpy.data.collections.new("Voxels")
            collection.children.link(voxels_col)
            bpy.ops.mesh.primitive_cube_add(location=center)
            bbox_obj = context.active_object
            bbox_obj.name = "0.Voxel"
            bbox_obj.scale = scale
            bbox_obj.display_type = 'WIRE'
            voxels_col.objects.link(bbox_obj)
            context.collection.objects.unlink(bbox_obj)
            root = "."
            level = max_level
            while level > 0:
                current_obj = lods.pop(0)
                wm.progress_update(max_level - level)
                print("=" * 60)
                print("Level:", level, "   using", current_obj.name)
                print("-" * 60)
                root = slicing.create_lods(current_obj, level, bbox)
                level = level - 1
            wm.progress_end()
            # Export current_obj as 0.glb
            bpy.ops.object.select_all(action='DESELECT')
            print("LODs still in list:", ", ".join([obj.name for obj in lods]))
            current_obj = lods.pop(0)
            current_obj.select_set(True)
            context.view_layer.objects.active = current_obj
            use_draco = context.scene.bbox_use_draco
            bpy.ops.export_scene.gltf(
                filepath=os.path.join(root, '0.glb'),
                export_format='GLB',
                use_selection=True,
                export_yup=False,
                export_normals=True,
                export_materials='NONE',
                export_draco_mesh_compression_enable=use_draco,
                export_draco_mesh_compression_level=6,
            )
            # List all GLB files in root
            files = [f for f in os.listdir(root) if f.endswith('.glb')]
            files.sort(key=lambda f: (len(f), f))
            lod_data = {
                "bbox": {
                    "min": bbox[0],
                    "max": bbox[1]
                },
                "files": files
            }
            lod_path = os.path.join(root, 'lod.json')
            with open(lod_path, 'w') as f:
                json.dump(lod_data, f, indent=4)
            # Restore active object
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            # Build report
            report_lines = [
                json.dumps({
                    "bbox": {
                        "min": bbox[0],
                        "max": bbox[1],
                        "center": [
                            (bbox[0][0] + bbox[1][0]) / 2,
                            (bbox[0][1] + bbox[1][1]) / 2,
                            (bbox[0][2] + bbox[1][2]) / 2,
                        ]
                    }
                }, indent=4),
                f"Output: {root}",
                f"Files: {len(files)}",
            ]
            context.scene.bbox_lod_report = "\n".join(report_lines)
            print("Done!")
            print("")
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class BBOX_OT_import_glb(bpy.types.Operator):
    bl_idname = "bbox.import_glb"
    bl_label = "Import GLB without transform"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.glb", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        before = set(context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=self.filepath)
        rot = mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
        for obj in set(context.scene.objects) - before:
            obj.matrix_world = rot @ obj.matrix_world
        return {'FINISHED'}


class BBOX_PT_panel(bpy.types.Panel):
    bl_label = "Bounding Box"
    bl_idname = "BBOX_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BBox"

    def draw(self, context):
        layout = self.layout
        layout.operator("bbox.import_glb")
        layout.separator()
        obj = context.active_object

        if obj is None:
            layout.label(text="Select an object")
            return

        layout.prop(context.scene, "bbox_force_cube")
        min_v, max_v = compute_bbox(obj, context.scene.bbox_force_cube)

        for axis, lo, hi in (("X:", min_v.x, max_v.x), ("Y:", min_v.y, max_v.y), ("Z:", min_v.z, max_v.z)):
            row = layout.split(factor=0.15, align=True)
            row.label(text=axis)
            # sub = row.row(align=True)
            sub = row.grid_flow(columns=2, row_major=True, even_columns=True, align=True)
            sub.label(text=f"{lo:.3f}")
            sub.label(text=f"{hi:.3f}")
        layout.separator()
        layout.operator("bbox.copy_to_clipboard")
        layout.separator()
        layout.operator("bbox.show_bounding_box")
        layout.operator("bbox.split_bounding_box")
        layout.separator()
        layout.prop(context.scene, "bbox_max_levels")
        layout.prop(context.scene, "bbox_use_draco")
        layout.operator("bbox.slice_lods")
        if context.scene.bbox_lod_report:
            box = layout.box()
            box.prop(context.scene, "bbox_lod_report_expanded",
                     icon='TRIA_DOWN' if context.scene.bbox_lod_report_expanded else 'TRIA_RIGHT',
                     text="Report", emboss=False)
            if context.scene.bbox_lod_report_expanded:
                col = box.column(align=True)
                col.scale_y = 0.6
                for line in context.scene.bbox_lod_report.split("\n"):
                    col.label(text=line)
                box.operator("bbox.copy_report")


classes = (BBOX_OT_copy, BBOX_OT_show, BBOX_OT_split, BBOX_OT_copy_report, BBOX_OT_lods, BBOX_OT_import_glb, BBOX_PT_panel)


def register():
    bpy.types.Scene.bbox_force_cube = bpy.props.BoolProperty(
        name="Force as regular Cube",
        default=True,
    )
    bpy.types.Scene.bbox_max_levels = bpy.props.IntProperty(
        name="Max levels",
        default=1,
        min=1,
        max=8,
    )
    bpy.types.Scene.bbox_use_draco = bpy.props.BoolProperty(
        name="Use DRACO compression",
        default=True,
    )
    bpy.types.Scene.bbox_lod_report = bpy.props.StringProperty(
        name="LOD Report",
        default="",
    )
    bpy.types.Scene.bbox_lod_report_expanded = bpy.props.BoolProperty(
        name="Show Report",
        default=True,
    )
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.bbox_lod_report_expanded
    del bpy.types.Scene.bbox_lod_report
    del bpy.types.Scene.bbox_use_draco
    del bpy.types.Scene.bbox_max_levels
    del bpy.types.Scene.bbox_force_cube
