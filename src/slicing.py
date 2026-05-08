import bpy
import bmesh
from mathutils import Vector
import json
import os
from . import utils

def get_level_collection(level):
    """Get or create a Level-{level} sub-collection inside Octree/Levels."""
    octree_collection = bpy.data.collections.get("Octree")
    levels_collection = octree_collection.children.get("Levels")
    if not levels_collection:
        levels_collection = bpy.data.collections.new("Levels")
        octree_collection.children.link(levels_collection)
    name = f"Level-{level}"
    existing = levels_collection.children.get(name)
    if existing:
        return existing
    col = bpy.data.collections.new(name)
    levels_collection.children.link(col)
    return col

def compute_center(bbox):
    (a, b) = bbox
    return (
        (a[0] + b[0]) / 2,
        (a[1] + b[1]) / 2,
        (a[2] + b[2]) / 2
    )

COLORS = (
    (0, 0, 0, 1),
    (1, 0, 0, 1),
    (0, 1, 0, 1),
    (1, 1, 0, 1),
    (0, 0, 1, 1),
    (1, 0, 1, 1),
    (0, 1, 1, 1),
    (1, 1, 1, 1),
)

def create_bbox(point_a, point_b, level):
    print(f"Create wireframe bbox from {point_a} to {point_b} for level {level}.")
    center = [
        (point_a[0] + point_b[0]) / 2,
        (point_a[1] + point_b[1]) / 2,
        (point_a[2] + point_b[2]) / 2
    ]
    scale = [
        abs(point_a[0] - point_b[0]) / 2,
        abs(point_a[1] - point_b[1]) / 2,
        abs(point_a[2] - point_b[2]) / 2
    ]
    # Get/create the target collection and set it as active
    octree_collection = bpy.data.collections.get("Octree")
    voxels = octree_collection.children.get("Voxels")
    if not voxels:
        voxels = bpy.data.collections.new("Voxels")
        octree_collection.children.link(voxels)
    voxel_level_name = f"Voxel-{level}"
    voxel_level = voxels.children.get(voxel_level_name)
    if not voxel_level:
        voxel_level = bpy.data.collections.new(voxel_level_name)
        voxels.children.link(voxel_level)
    layer_collection = utils.find_layer_collection(bpy.context.view_layer.layer_collection, voxel_level_name)
    bpy.context.view_layer.active_layer_collection = layer_collection

    bpy.ops.mesh.primitive_cube_add(location=center)
    obj = bpy.context.active_object
    obj.name = "bbox"
    obj.scale = scale
    obj.display_type = 'WIRE'
    mat = bpy.data.materials.new(name=f"bbox_edge_color_{level}")
    mat.use_nodes = False
    color = COLORS[level % len(COLORS)]
    mat.diffuse_color = color
    obj.data.materials.append(mat)
    obj.color = color
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.color_type = 'OBJECT'
            break
    return obj
    
    
def save_mesh_as_glb(obj):
    """
    Exports the given object to GLB in the same folder as the .blend file.
    Filename: [Object_Name].glb
    Settings: Normals included, No Materials, Y+ Up, Draco Compression (if enabled).
    """
    blend_file_path = bpy.data.filepath
    if not blend_file_path:
        raise RuntimeError("Please save your Blender file before running this script.")

    directory = os.path.dirname(blend_file_path)
    name = obj.name.removeprefix("Octree")
    filename = f"{name}.glb"
    export_path = os.path.join(directory, "Octree", filename)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    use_draco = bpy.context.scene.bbox_use_draco
    bpy.ops.export_scene.gltf(
        filepath=export_path,
        export_format='GLB',
        use_selection=True,
        export_yup=False,
        export_normals=True,
        export_materials='NONE',
        export_draco_mesh_compression_enable=use_draco,
        export_draco_mesh_compression_level=6
    )
    print(f"Successfully exported: {export_path}")

# --- Example of how to call it ---
# active_obj = bpy.context.active_object
# if active_obj:
#     save_mesh_as_glb(active_obj)

def bisect(obj_parent, normal, center, collection):
    children = []
    for part in (0, 1):    
        obj = utils.clone(obj_parent, obj_parent.name + str(part))
        collection.objects.link(obj)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=Vector(center),
            plane_no=normal,
            clear_inner=(part == 1),
            clear_outer=(part == 0)
        )
        bm.to_mesh(obj.data)
        bm.free()
        children.append(obj)
    utils.remove(obj_parent)
    return children

def slice_z(obj_parent, bbox, levels, level):
    col = get_level_collection(levels)
    if level < levels:
        center = compute_center(bbox)
        normal = (0, 0, 1)
        (obj0, obj1) = bisect(obj_parent, normal, center, col)
        if len(obj0.data.vertices) == 0:
            bpy.data.objects.remove(obj0, do_unlink=True)
        else:
            bbox0 = (bbox[0][:], bbox[1][:])
            bbox0[1][2] = center[2]
            slice_z(obj0, bbox0, levels, level + 1)
        if len(obj1.data.vertices) == 0:
            bpy.data.objects.remove(obj1, do_unlink=True)
        else:            
            bbox1 = (bbox[0][:], bbox[1][:])
            bbox1[0][2] = center[2]
            slice_z(obj1, bbox1, levels, level + 1)
    else:
        obj_parent.name = obj_parent.name.removeprefix("Octree")
        print(f"Block {obj_parent.name} has {len(obj_parent.data.vertices)} vertices")
        create_bbox(bbox[0], bbox[1], levels)
        save_mesh_as_glb(obj_parent)
        
def slice_y(obj_parent, bbox, levels, level):
    col = get_level_collection(levels)
    if level < levels:
        center = compute_center(bbox)
        normal = (0, 1, 0)
        (obj0, obj1) = bisect(obj_parent, normal, center, col)
        if len(obj0.data.vertices) == 0:
            bpy.data.objects.remove(obj0, do_unlink=True)
        else:
            bbox0 = (bbox[0][:], bbox[1][:])
            bbox0[1][1] = center[1]
            slice_y(obj0, bbox0, levels, level + 1)
        if len(obj1.data.vertices) == 0:
            bpy.data.objects.remove(obj1, do_unlink=True)
        else:            
            bbox1 = (bbox[0][:], bbox[1][:])
            bbox1[0][1] = center[1]
            slice_y(obj1, bbox1, levels, level + 1)
    else:
        slice_z(obj_parent, bbox, levels, 0)
    
def slice_x(obj_parent, bbox, levels, level):
    col = get_level_collection(levels)
    if level < levels:
        center = compute_center(bbox)
        normal = (1, 0, 0)
        (obj0, obj1) = bisect(obj_parent, normal, center, col)
        if len(obj0.data.vertices) == 0:
            bpy.data.objects.remove(obj0, do_unlink=True)
        else:
            bbox0 = (bbox[0][:], bbox[1][:])
            bbox0[1][0] = center[0]
            slice_x(obj0, bbox0, levels, level + 1)
        if len(obj1.data.vertices) == 0:
            bpy.data.objects.remove(obj1, do_unlink=True)
        else:            
            bbox1 = (bbox[0][:], bbox[1][:])
            bbox1[0][0] = center[0]
            slice_x(obj1, bbox1, levels, level + 1)
    else:
        slice_y(obj_parent, bbox, levels, 0)
    
def slice(obj, levels, bbox):
    obj.name = "Octree"
    slice_x(obj, bbox, levels, 0)

def create_lods(active_obj, levels, bbox):
    if active_obj and active_obj.type == 'MESH':
        blend_filepath = bpy.data.filepath
        if not blend_filepath:
            raise RuntimeError("Save your Blender file first to define a directory!")
        directory = os.path.dirname(blend_filepath)
        root = os.path.join(directory, "Octree")
        if not os.path.exists(root):
            os.mkdir(root)

        obj = utils.clone(active_obj, "Octree")
        print(f"Starting the slicing for level {levels}...")
        slice(obj, levels, bbox)
        return root
    else:
        raise RuntimeError("No active mesh object selected!")

