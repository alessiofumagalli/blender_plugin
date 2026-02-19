bl_info = {
    "name": "Transform Geometry with Pivot",
    "author": "Gerardo Cicalese",
    "version": (1, 0, 0),
    "blender": (4, 0, 0), # Change this to your specific Blender version if needed
    "location": "Node Editor > Add Menu",
    "description": "Adds a custom node group to rotate and scale geometry around a specific pivot point.",
    "warning": "",
    "doc_url": "",
    "category": "Node",
}

import bpy
import mathutils
import os
import typing

def create_pivot_node_group(node_tree_names: dict[typing.Callable, str]):
    """Initialize Transform Geometry with Pivot node group"""
    tree = bpy.data.node_groups.new(type='GeometryNodeTree', name="Transform Geometry with Pivot")

    tree.color_tag = 'NONE'
    tree.description = ""
    tree.default_group_node_width = 140
    
    if hasattr(tree, "show_modifier_manage_panel"):
        tree.show_modifier_manage_panel = True

    # --- Interface Setup ---
    geometry_socket = tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'
    geometry_socket.default_input = 'VALUE'
    geometry_socket.structure_type = 'AUTO'

    transform_socket = tree.interface.new_socket(name="Transform", in_out='INPUT', socket_type='NodeSocketMatrix')
    transform_socket.attribute_domain = 'POINT'
    transform_socket.default_input = 'VALUE'
    transform_socket.structure_type = 'AUTO'

    geometry_socket_1 = tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'
    geometry_socket_1.description = "Geometry to transform"
    geometry_socket_1.default_input = 'VALUE'
    geometry_socket_1.structure_type = 'AUTO'

    # --- Node Setup ---
    group_output = tree.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    group_input = tree.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    transform_geometry = tree.nodes.new("GeometryNodeTransform")
    transform_geometry.name = "Transform Geometry"
    transform_geometry.inputs[1].default_value = 'Matrix' 
    transform_geometry.inputs[2].default_value = (0.0, 0.0, 0.0) 
    transform_geometry.inputs[3].default_value = (0.0, 0.0, 0.0) 
    transform_geometry.inputs[4].default_value = (2.0, 1.0, 1.0) 

    # Node Self Object (Replaces the hardcoded "Sphere")
    self_object = tree.nodes.new("GeometryNodeSelfObject")
    self_object.name = "Self Object"

    # Node Object Info.001
    object_info_001 = tree.nodes.new("GeometryNodeObjectInfo")
    object_info_001.name = "Object Info.001"
    object_info_001.transform_space = 'ORIGINAL' # Grabs global location
    object_info_001.inputs[1].default_value = False 

    transform_geometry_001 = tree.nodes.new("GeometryNodeTransform")
    transform_geometry_001.name = "Transform Geometry.001"
    transform_geometry_001.inputs[1].default_value = 'Components' 
    transform_geometry_001.inputs[3].default_value = (0.0, 0.0, 0.0) 
    transform_geometry_001.inputs[4].default_value = (1.0, 1.0, 1.0) 

    vector_math = tree.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'SUBTRACT'
    vector_math.inputs[0].default_value = (0.0, 0.0, 0.0) 

    transform_geometry_002 = tree.nodes.new("GeometryNodeTransform")
    transform_geometry_002.name = "Transform Geometry.002"
    transform_geometry_002.inputs[1].default_value = 'Components' 
    transform_geometry_002.inputs[3].default_value = (0.0, 0.0, 0.0) 
    transform_geometry_002.inputs[4].default_value = (1.0, 1.0, 1.0) 

    # --- Set locations ---
    tree.nodes["Group Output"].location = (763.5, 0.0)
    tree.nodes["Group Input"].location = (-773.5, 0.0)
    tree.nodes["Transform Geometry"].location = (256.0, 182.1)
    tree.nodes["Self Object"].location = (-750.0, -22.4)
    tree.nodes["Object Info.001"].location = (-573.5, -22.4)
    tree.nodes["Transform Geometry.001"].location = (-64.7, -96.9)
    tree.nodes["Vector Math"].location = (-315.9, -182.1)
    tree.nodes["Transform Geometry.002"].location = (573.5, -19.6)

    # --- Initialize links ---
    # Link Self Object -> Object Info
    tree.links.new(tree.nodes["Self Object"].outputs[0], tree.nodes["Object Info.001"].inputs[0])
    
    tree.links.new(tree.nodes["Transform Geometry"].outputs[0], tree.nodes["Transform Geometry.002"].inputs[0])
    tree.links.new(tree.nodes["Object Info.001"].outputs[1], tree.nodes["Transform Geometry.001"].inputs[2])
    tree.links.new(tree.nodes["Object Info.001"].outputs[1], tree.nodes["Vector Math"].inputs[1])
    tree.links.new(tree.nodes["Vector Math"].outputs[0], tree.nodes["Transform Geometry.002"].inputs[2])
    tree.links.new(tree.nodes["Transform Geometry.001"].outputs[0], tree.nodes["Transform Geometry"].inputs[0])
    tree.links.new(tree.nodes["Group Input"].outputs[0], tree.nodes["Transform Geometry"].inputs[5])
    tree.links.new(tree.nodes["Group Input"].outputs[1], tree.nodes["Transform Geometry.001"].inputs[0])
    tree.links.new(tree.nodes["Transform Geometry.002"].outputs[0], tree.nodes["Group Output"].inputs[0])

    return tree

# --- Operator & Registration ---

class NODE_OT_pivot_transform(bpy.types.Operator):
    bl_idname = "node.add_pivot_transform" 
    bl_label = "Transform Geometry with Pivot"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context):
        node_tree_names: dict[typing.Callable, str] = {}
        tree = create_pivot_node_group(node_tree_names)
        node_tree_names[create_pivot_node_group] = tree.name
        
        if context.space_data and context.space_data.type == 'NODE_EDITOR':
            active_tree = context.space_data.edit_tree
            if active_tree:
                new_node = active_tree.nodes.new('GeometryNodeGroup')
                new_node.node_tree = tree
                new_node.location = context.space_data.cursor_location
                
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(NODE_OT_pivot_transform.bl_idname)

classes = [
    NODE_OT_pivot_transform,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_add.append(menu_func)

def unregister():
    bpy.types.NODE_MT_add.remove(menu_func)
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()