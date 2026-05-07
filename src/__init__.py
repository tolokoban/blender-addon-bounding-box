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
import mathutils


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


class BBOX_PT_panel(bpy.types.Panel):
    bl_label = "Bounding Box"
    bl_idname = "BBOX_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BBox"

    def draw(self, context):
        layout = self.layout
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


classes = (BBOX_OT_copy, BBOX_OT_show, BBOX_OT_split, BBOX_PT_panel)


def register():
    bpy.types.Scene.bbox_force_cube = bpy.props.BoolProperty(
        name="Force as regular Cube",
        default=True,
    )
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.bbox_force_cube
