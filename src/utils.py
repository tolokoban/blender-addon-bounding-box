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
    bpy.data.objects.remove(obj, do_unlink=True)


def clone(obj, name):
    new_obj = obj.copy()
    new_obj.data = obj.data.copy()
    new_obj.name = name
    return new_obj
