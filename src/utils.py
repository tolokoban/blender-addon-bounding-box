import bpy


def find_layer_collection(layer_collection, name):
    """Recursively find a LayerCollection by collection name."""
    if layer_collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        result = find_layer_collection(child, name)
        if result:
            return result
    return None


def remove(obj):
    """Remove an object from the blend file and unlink it from all collections."""
    bpy.data.objects.remove(obj, do_unlink=True)


def clone(obj, name):
    """Create a deep copy of an object with all transforms applied."""
    new_obj = obj.copy()
    new_obj.data = obj.data.copy()
    new_obj.name = name
    bpy.context.collection.objects.link(new_obj)
    bpy.context.view_layer.objects.active = new_obj
    new_obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    new_obj.select_set(False)
    bpy.context.collection.objects.unlink(new_obj)
    return new_obj
