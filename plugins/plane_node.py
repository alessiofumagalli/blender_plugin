bl_info = {
    "name": "Plane From Point + Normal",
    "author": "Camilla Crippa",
    "version": (1, 0, 3),
    "blender": (5, 0, 0),
    "location": "Geometry Nodes > Add",
    "description": "Creates a plane oriented by a Normal vector and passing through a Point (Blender 5.0 safe)",
    "category": "Node",
}

import bpy

GROUP_NAME = "Plane From Point + Normal"


def ensure_socket(iface, name, in_out, socket_type, default=None, *, min_value=None):
    sock = next((s for s in iface.items_tree if s.name == name and s.in_out == in_out), None)
    if not sock:
        sock = iface.new_socket(name, socket_type=socket_type, in_out=in_out)

    if default is not None and hasattr(sock, "default_value"):
        sock.default_value = default

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


def out_sock(node, candidates, fallback_index=0):
    for nm in candidates:
        if nm in node.outputs:
            return node.outputs[nm]
    return node.outputs[min(fallback_index, len(node.outputs) - 1)]


def in_sock(node, candidates, fallback_index=0):
    for nm in candidates:
        if nm in node.inputs:
            return node.inputs[nm]
    return node.inputs[min(fallback_index, len(node.inputs) - 1)]


def build_plane_from_point_normal_group():
    # Remove existing group so old sockets don't linger
    if GROUP_NAME in bpy.data.node_groups:
        old = bpy.data.node_groups[GROUP_NAME]
        bpy.data.node_groups.remove(old, do_unlink=True)

    ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    iface = ng.interface

    # Inputs / Outputs (NO Resolution)
    ensure_socket(iface, "Point", "INPUT", "NodeSocketVector", (0.0, 0.0, 0.0))
    ensure_socket(iface, "Normal", "INPUT", "NodeSocketVector", (0.0, 0.0, 1.0))
    ensure_socket(iface, "Size", "INPUT", "NodeSocketFloat", 2.0, min_value=0.0)
    ensure_socket(iface, "Geometry", "OUTPUT", "NodeSocketGeometry")

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-1200, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (900, 0)

    # -------------------------
    # Safety clamp: Size >= 0
    # -------------------------
    n_size_pos = nodes.new("ShaderNodeMath")
    n_size_pos.operation = "MAXIMUM"
    n_size_pos.location = (-950, 200)
    links.new(n_in.outputs["Size"], n_size_pos.inputs[0])
    n_size_pos.inputs[1].default_value = 0.0

    # -------------------------
    # Create base plane (Grid) - robust across Blender builds
    # -------------------------
    n_grid = new_node(
        nodes,
        "GeometryNodeMeshGrid",           # common
        "GeometryNodeMeshPrimitiveGrid",  # fallback
    )
    n_grid.location = (-700, 200)

    def link_if_input_exists(node, input_names, from_socket):
        for nm in input_names:
            if nm in node.inputs:
                links.new(from_socket, node.inputs[nm])
                return True
        return False

    # Size axis 1
    if not link_if_input_exists(n_grid, ["Size X", "Size U", "Width"], n_size_pos.outputs[0]):
        if "Size" in n_grid.inputs:
            links.new(n_size_pos.outputs[0], n_grid.inputs["Size"])

    # Size axis 2
    link_if_input_exists(n_grid, ["Size Y", "Size V", "Height"], n_size_pos.outputs[0])

    # -------------------------
    # Normal: normalize + handle zero vector (robust)
    # -------------------------
    # length(Normal)
    n_len = nodes.new("ShaderNodeVectorMath")
    n_len.operation = "LENGTH"
    n_len.location = (-700, -120)
    links.new(n_in.outputs["Normal"], n_len.inputs[0])
    len_out = out_sock(n_len, ["Value"], fallback_index=0)

    # (length > eps) ?
    n_gt = nodes.new("ShaderNodeMath")
    n_gt.operation = "GREATER_THAN"
    n_gt.location = (-480, -120)
    links.new(len_out, n_gt.inputs[0])
    n_gt.inputs[1].default_value = 1e-12

    # Normalize normal
    n_norm = nodes.new("ShaderNodeVectorMath")
    n_norm.operation = "NORMALIZE"
    n_norm.location = (-700, -260)
    links.new(n_in.outputs["Normal"], n_norm.inputs[0])
    norm_out = out_sock(n_norm, ["Vector"], fallback_index=0)

    # Mix between (0,0,1) and normalized normal based on gt
    n_mix = nodes.new("ShaderNodeMix")
    n_mix.location = (-250, -220)
    n_mix.data_type = "VECTOR"

    links.new(out_sock(n_gt, ["Value"], fallback_index=0), in_sock(n_mix, ["Factor"], fallback_index=0))
    in_sock(n_mix, ["A"], fallback_index=1).default_value = (0.0, 0.0, 1.0)
    links.new(norm_out, in_sock(n_mix, ["B"], fallback_index=2))
    mix_out = out_sock(n_mix, ["Result"], fallback_index=0)

    # -------------------------
    # Align Z axis to Normal
    # -------------------------
    n_align = new_node(nodes, "FunctionNodeAlignEulerToVector", "GeometryNodeAlignEulerToVector")
    n_align.location = (-50, -220)
    if hasattr(n_align, "axis"):
        n_align.axis = "Z"

    links.new(mix_out, in_sock(n_align, ["Vector"], fallback_index=0))

    # -------------------------
    # Transform Geometry:
    # Rotation = aligned, Translation = Point
    # -------------------------
    n_xform = nodes.new("GeometryNodeTransform")
    n_xform.location = (350, 120)
    links.new(out_sock(n_grid, ["Mesh", "Geometry"], fallback_index=0), n_xform.inputs["Geometry"])
    links.new(out_sock(n_align, ["Rotation"], fallback_index=0), n_xform.inputs["Rotation"])
    links.new(n_in.outputs["Point"], n_xform.inputs["Translation"])

    # Output
    links.new(n_xform.outputs["Geometry"], n_out.inputs["Geometry"])

    return ng


class NODE_OT_add_plane_from_point_normal(bpy.types.Operator):
    bl_idname = "node.add_plane_from_point_normal"
    bl_label = "Plane From Point + Normal"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ng = build_plane_from_point_normal_group()

        tree = context.space_data.edit_tree
        node = tree.nodes.new("GeometryNodeGroup")
        node.node_tree = ng
        node.label = GROUP_NAME
        node.location = getattr(context.space_data, "cursor_location", (0, 0))

        out = next((n for n in tree.nodes if n.bl_idname == "NodeGroupOutput"), None)
        if out and "Geometry" in node.outputs and "Geometry" in out.inputs:
            tree.links.new(node.outputs["Geometry"], out.inputs["Geometry"])

        return {"FINISHED"}


def menu_func(self, context):
    if context.space_data.tree_type == "GeometryNodeTree":
        self.layout.operator(
            NODE_OT_add_plane_from_point_normal.bl_idname,
            text="Plane From Point + Normal",
            icon="MESH_GRID",
        )


def register():
    bpy.utils.register_class(NODE_OT_add_plane_from_point_normal)
    bpy.types.NODE_MT_add.append(menu_func)


def unregister():
    bpy.types.NODE_MT_add.remove(menu_func)
    bpy.utils.unregister_class(NODE_OT_add_plane_from_point_normal)


if __name__ == "__main__":
    register()
