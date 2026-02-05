bl_info = {
    "name": "Vector Arrow",
    "author": "Camilla Crippa",
    "version": (1, 2, 3),
    "blender": (5, 0, 0),
    "location": "Geometry Nodes > Add",
    "description": "Vector arrow primitive built from curves (Blender 5.0 safe) + cone arrow head",
    "category": "Node",
}

import bpy

GROUP_NAME = "Vector Arrow"


def ensure_socket(iface, name, in_out, socket_type, default=None, *, min_value=None):
    sock = next(
        (s for s in iface.items_tree if s.name == name and s.in_out == in_out),
        None,
    )
    if not sock:
        sock = iface.new_socket(name, socket_type=socket_type, in_out=in_out)

    if default is not None and hasattr(sock, "default_value"):
        sock.default_value = default

    # clamp UI range (prevents going below 0 in the group interface)
    if min_value is not None and hasattr(sock, "min_value"):
        try:
            sock.min_value = min_value
        except Exception:
            pass

    return sock


def new_node(nodes, *idnames):
    """Try multiple node idnames for compatibility."""
    last_err = None
    for idn in idnames:
        try:
            return nodes.new(idn)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"None of these node types exist: {idnames}. Last error: {last_err}")


def build_vector_arrow_group():
    # IMPORTANT: se esiste già, eliminalo (così spariscono anche i vecchi socket tipo "Radius")
    if GROUP_NAME in bpy.data.node_groups:
        old = bpy.data.node_groups[GROUP_NAME]
        bpy.data.node_groups.remove(old, do_unlink=True)

    # ricrea sempre da zero
    ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")

    iface = ng.interface

    # INPUTS / OUTPUTS (NO "Radius")
    ensure_socket(iface, "Start", "INPUT", "NodeSocketVector", (0, 0, 0))
    ensure_socket(iface, "Vector", "INPUT", "NodeSocketVector", (1, 0, 0))
    ensure_socket(iface, "Scale", "INPUT", "NodeSocketFloat", 0.03, min_value=0.0)
    ensure_socket(iface, "Geometry", "OUTPUT", "NodeSocketGeometry")

    nodes = ng.nodes
    links = ng.links

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-1200, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (1500, 0)

    # -------------------------
    # Scale >= 0 (safety clamp)
    # -------------------------
    n_scale_pos = nodes.new("ShaderNodeMath")
    n_scale_pos.operation = "MAXIMUM"
    n_scale_pos.location = (-950, -50)
    links.new(n_in.outputs["Scale"], n_scale_pos.inputs[0])
    n_scale_pos.inputs[1].default_value = 0.0

    # -------------------------
    # End = Start + Vector
    # -------------------------
    n_end = nodes.new("ShaderNodeVectorMath")
    n_end.operation = "ADD"
    n_end.location = (-700, 200)
    links.new(n_in.outputs["Start"], n_end.inputs[0])
    links.new(n_in.outputs["Vector"], n_end.inputs[1])

    # Curve Line
    n_curve = nodes.new("GeometryNodeCurvePrimitiveLine")
    n_curve.location = (-500, 200)
    links.new(n_in.outputs["Start"], n_curve.inputs["Start"])
    links.new(n_end.outputs[0], n_curve.inputs["End"])

    # Resample Curve
    n_resample = nodes.new("GeometryNodeResampleCurve")
    n_resample.location = (-300, 200)
    n_resample.inputs["Count"].default_value = 16
    links.new(n_curve.outputs["Curve"], n_resample.inputs["Curve"])

    # Spline Parameter
    n_param = nodes.new("GeometryNodeSplineParameter")
    n_param.location = (-300, 0)

    # Taper near end
    n_map = nodes.new("ShaderNodeMapRange")
    n_map.location = (-100, 0)
    n_map.inputs["From Min"].default_value = 0.8
    n_map.inputs["From Max"].default_value = 1.0
    n_map.inputs["To Min"].default_value = 1.0
    n_map.inputs["To Max"].default_value = 3.0
    links.new(n_param.outputs["Factor"], n_map.inputs["Value"])

    # scale_pos * mapped factor
    n_mul = nodes.new("ShaderNodeMath")
    n_mul.operation = "MULTIPLY"
    n_mul.location = (100, 0)
    links.new(n_map.outputs[0], n_mul.inputs[0])
    links.new(n_scale_pos.outputs[0], n_mul.inputs[1])

    # Set Curve Radius (uses computed thickness)
    n_set_curve_radius = nodes.new("GeometryNodeSetCurveRadius")
    n_set_curve_radius.location = (100, 200)
    links.new(n_resample.outputs["Curve"], n_set_curve_radius.inputs["Curve"])
    links.new(n_mul.outputs[0], n_set_curve_radius.inputs["Radius"])

    # Profile circle
    n_circle = nodes.new("GeometryNodeCurvePrimitiveCircle")
    n_circle.location = (300, 0)
    links.new(n_scale_pos.outputs[0], n_circle.inputs["Radius"])

    # Curve to Mesh (tube)
    n_mesh = nodes.new("GeometryNodeCurveToMesh")
    n_mesh.location = (500, 200)
    links.new(n_set_curve_radius.outputs["Curve"], n_mesh.inputs["Curve"])
    links.new(n_circle.outputs["Curve"], n_mesh.inputs["Profile Curve"])

    # =========================
    # ARROW HEAD (CONE AT END)
    # =========================

    # Single point geometry (Mesh Line with 1 point)
    n_point = nodes.new("GeometryNodeMeshLine")
    n_point.location = (-100, -250)
    n_point.inputs["Count"].default_value = 1
    n_point.inputs["Offset"].default_value = (0.0, 0.0, 0.0)

    # Place that point at End
    n_set_pos = nodes.new("GeometryNodeSetPosition")
    n_set_pos.location = (100, -250)
    links.new(n_point.outputs["Mesh"], n_set_pos.inputs["Geometry"])
    links.new(n_end.outputs[0], n_set_pos.inputs["Position"])

    # Cone mesh for the head
    n_cone = nodes.new("GeometryNodeMeshCone")
    n_cone.location = (300, -350)
    n_cone.inputs["Vertices"].default_value = 16
    n_cone.inputs["Radius Top"].default_value = 0.0  # pointy tip

    # Head base = scale_pos * 2.5
    n_head_base = nodes.new("ShaderNodeMath")
    n_head_base.operation = "MULTIPLY"
    n_head_base.location = (300, -200)
    n_head_base.inputs[1].default_value = 2.5
    links.new(n_scale_pos.outputs[0], n_head_base.inputs[0])
    links.new(n_head_base.outputs[0], n_cone.inputs["Radius Bottom"])

    # Head height = scale_pos * 6.0
    n_head_h = nodes.new("ShaderNodeMath")
    n_head_h.operation = "MULTIPLY"
    n_head_h.location = (500, -200)
    n_head_h.inputs[1].default_value = 6.0
    links.new(n_scale_pos.outputs[0], n_head_h.inputs[0])
    links.new(n_head_h.outputs[0], n_cone.inputs["Depth"])

    # Instance cone on end point
    n_instance = nodes.new("GeometryNodeInstanceOnPoints")
    n_instance.location = (600, -300)
    links.new(n_set_pos.outputs["Geometry"], n_instance.inputs["Points"])
    links.new(n_cone.outputs["Mesh"], n_instance.inputs["Instance"])

    # Align to vector direction
    n_align = new_node(nodes, "FunctionNodeAlignEulerToVector", "GeometryNodeAlignEulerToVector")
    n_align.location = (800, -300)
    if hasattr(n_align, "axis"):
        n_align.axis = "Z"

    if "Vector" in n_align.inputs:
        links.new(n_in.outputs["Vector"], n_align.inputs["Vector"])
    else:
        links.new(n_in.outputs["Vector"], n_align.inputs[0])

    n_rot = nodes.new("GeometryNodeRotateInstances")
    n_rot.location = (1000, -300)
    links.new(n_instance.outputs["Instances"], n_rot.inputs["Instances"])
    links.new(n_align.outputs["Rotation"], n_rot.inputs["Rotation"])

    # Realize instances
    n_realize = nodes.new("GeometryNodeRealizeInstances")
    n_realize.location = (1200, -300)
    links.new(n_rot.outputs["Instances"], n_realize.inputs["Geometry"])

    # Join tube + head
    n_join = nodes.new("GeometryNodeJoinGeometry")
    n_join.location = (1200, 150)
    links.new(n_mesh.outputs["Mesh"], n_join.inputs["Geometry"])
    links.new(n_realize.outputs["Geometry"], n_join.inputs["Geometry"])

    # Output
    links.new(n_join.outputs["Geometry"], n_out.inputs["Geometry"])

    return ng


class NODE_OT_add_vector_arrow(bpy.types.Operator):
    bl_idname = "node.add_vector_arrow"
    bl_label = "Vector Arrow"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ng = build_vector_arrow_group()
        tree = context.space_data.edit_tree
        node = tree.nodes.new("GeometryNodeGroup")
        node.node_tree = ng
        node.label = GROUP_NAME
        node.location = getattr(context.space_data, "cursor_location", (0, 0))

        out = next((n for n in tree.nodes if n.bl_idname == "NodeGroupOutput"), None)
        if out:
            tree.links.new(node.outputs["Geometry"], out.inputs["Geometry"])

        return {"FINISHED"}


def menu_func(self, context):
    if context.space_data.tree_type == "GeometryNodeTree":
        self.layout.operator(
            NODE_OT_add_vector_arrow.bl_idname,
            text="Vector Arrow",
            icon="EMPTY_ARROWS",
        )


def register():
    bpy.utils.register_class(NODE_OT_add_vector_arrow)
    bpy.types.NODE_MT_add.append(menu_func)


def unregister():
    bpy.types.NODE_MT_add.remove(menu_func)
    bpy.utils.unregister_class(NODE_OT_add_vector_arrow)


if __name__ == "__main__":
    register()
