bl_info = {
    "name": "Bezier From 4 Points",
    "author": "Camilla Crippa",
    "version": (1, 3, 0),
    "blender": (5, 0, 0),
    "location": "Geometry Nodes > Add",
    "description": "Build a Bezier curve from 2/3/4 inputs with explicit toggles (line/quadratic/cubic) converted to cubic. Index fixed to 0.",
    "category": "Node",
}

import bpy

GROUP_NAME = "Bezier From 4 Points"


# -------------------------------
# Interface socket helper
# -------------------------------
def ensure_socket(iface, name, in_out, socket_type, default=None, *, min_value=None, max_value=None):
    sock = next(
        (s for s in iface.items_tree if s.name == name and getattr(s, "in_out", None) == in_out),
        None,
    )
    if not sock:
        sock = iface.new_socket(name, socket_type=socket_type, in_out=in_out)

    if default is not None and hasattr(sock, "default_value"):
        sock.default_value = default
    if min_value is not None and hasattr(sock, "min_value"):
        sock.min_value = min_value
    if max_value is not None and hasattr(sock, "max_value"):
        sock.max_value = max_value
    return sock


def _find_socket(sockets, names):
    for nm in names:
        s = sockets.get(nm)
        if s is not None:
            return s
    return None


def _link(links, out_socket, in_socket):
    if out_socket and in_socket:
        links.new(out_socket, in_socket)


def build_group():
    # Create or reuse the group
    if GROUP_NAME in bpy.data.node_groups:
        ng = bpy.data.node_groups[GROUP_NAME]
        ng.nodes.clear()
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")

    iface = ng.interface

    # Inputs: 4 geometries (Points-like), toggles, Resolution
    ensure_socket(iface, "P0", "INPUT", "NodeSocketGeometry")
    ensure_socket(iface, "P1", "INPUT", "NodeSocketGeometry")
    ensure_socket(iface, "P2", "INPUT", "NodeSocketGeometry")
    ensure_socket(iface, "P3", "INPUT", "NodeSocketGeometry")

    ensure_socket(iface, "Use P2 (Quadratic)", "INPUT", "NodeSocketBool", default=False)
    ensure_socket(iface, "Use P3 (Cubic)", "INPUT", "NodeSocketBool", default=False)

    ensure_socket(iface, "Resolution", "INPUT", "NodeSocketInt", default=32, min_value=1)

    ensure_socket(iface, "Curve", "OUTPUT", "NodeSocketGeometry")

    nodes = ng.nodes
    links = ng.links

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-1100, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (980, 0)

    # ---- helpers ----
    def make_value(val, loc):
        n = nodes.new("ShaderNodeValue")
        n.location = loc
        n.outputs[0].default_value = float(val)
        return n.outputs[0]

    def vec_math(op, loc):
        n = nodes.new("ShaderNodeVectorMath")
        n.location = loc
        n.operation = op
        return n

    def switch_vec(loc):
        n = nodes.new("GeometryNodeSwitch")
        n.location = loc
        n.input_type = "VECTOR"
        return n

    # -----------------------------------------
    # Sample index position from each input geo
    # Index is fixed to 0 internally
    # -----------------------------------------
    def sample_pos(label, geo_socket_name, loc):
        realize = nodes.new("GeometryNodeRealizeInstances")
        realize.location = (loc[0] - 260, loc[1])
        _link(links, n_in.outputs[geo_socket_name], _find_socket(realize.inputs, ["Geometry"]))

        samp = nodes.new("GeometryNodeSampleIndex")
        samp.location = loc
        samp.data_type = "FLOAT_VECTOR"
        samp.domain = "POINT"

        _link(links, _find_socket(realize.outputs, ["Geometry"]), _find_socket(samp.inputs, ["Geometry"]))

        # Index = 0 (constant)
        idx0 = nodes.new("FunctionNodeInputInt")
        idx0.location = (loc[0] - 260, loc[1] - 140)
        idx0.integer = 0
        _link(links, _find_socket(idx0.outputs, ["Integer"]), _find_socket(samp.inputs, ["Index"]))

        pos = nodes.new("GeometryNodeInputPosition")
        pos.location = (loc[0] - 220, loc[1] - 240)
        _link(links, pos.outputs["Position"], _find_socket(samp.inputs, ["Value"]))

        samp.label = label
        return _find_socket(samp.outputs, ["Value"])

    p0 = sample_pos("P0 sample", "P0", (-720, 260))
    p1 = sample_pos("P1 sample", "P1", (-720, 80))
    p2 = sample_pos("P2 sample", "P2", (-720, -100))
    p3 = sample_pos("P3 sample", "P3", (-720, -280))

    # -----------------------------------------
    # Degree selection (explicit toggles)
    # - If Use P3 ON => cubic
    # - Else if Use P2 ON => quadratic
    # - Else => linear
    # -----------------------------------------
    use_p2 = n_in.outputs["Use P2 (Quadratic)"]
    use_p3 = n_in.outputs["Use P3 (Cubic)"]

    not_use_p3 = nodes.new("FunctionNodeBooleanMath")
    not_use_p3.location = (-420, -10)
    not_use_p3.operation = "NOT"
    _link(links, use_p3, _find_socket(not_use_p3.inputs, ["Boolean"]))

    quad_enabled = nodes.new("FunctionNodeBooleanMath")
    quad_enabled.location = (-240, -10)
    quad_enabled.operation = "AND"
    _link(links, use_p2, _find_socket(quad_enabled.inputs, ["Boolean"]))
    _link(links, _find_socket(not_use_p3.outputs, ["Boolean"]), _find_socket(quad_enabled.inputs, ["Boolean_001"]))

    # -----------------------------------------
    # Select END point
    # linear: end = p1
    # quadratic: end = p2
    # cubic: end = p3
    # -----------------------------------------
    sw_end_lin_quad = switch_vec((-40, 120))
    _link(links, _find_socket(quad_enabled.outputs, ["Boolean"]), _find_socket(sw_end_lin_quad.inputs, ["Switch"]))
    _link(links, p1, _find_socket(sw_end_lin_quad.inputs, ["False"]))
    _link(links, p2, _find_socket(sw_end_lin_quad.inputs, ["True"]))

    sw_end_cubic = switch_vec((160, 120))
    _link(links, use_p3, _find_socket(sw_end_cubic.inputs, ["Switch"]))
    _link(links, _find_socket(sw_end_lin_quad.outputs, ["Output"]), _find_socket(sw_end_cubic.inputs, ["False"]))
    _link(links, p3, _find_socket(sw_end_cubic.inputs, ["True"]))

    end_pt = _find_socket(sw_end_cubic.outputs, ["Output"])

    # -----------------------------------------
    # Build cubic handles
    # - Linear conversion (P0 -> end)
    # - Quadratic conversion (P0, control=P1, end)
    # - Cubic direct (handles: P1, P2)
    # -----------------------------------------
    one_third = make_value(1.0 / 3.0, (0, 340))
    two_third = make_value(2.0 / 3.0, (0, 300))

    # Linear handles from P0 and end_pt
    v_end_minus_p0 = vec_math("SUBTRACT", (160, 340))
    _link(links, end_pt, _find_socket(v_end_minus_p0.inputs, ["Vector"]))
    _link(links, p0, _find_socket(v_end_minus_p0.inputs, ["Vector_001"]))

    v_d_over3 = vec_math("SCALE", (360, 340))
    _link(links, _find_socket(v_end_minus_p0.outputs, ["Vector"]), _find_socket(v_d_over3.inputs, ["Vector"]))
    _link(links, one_third, _find_socket(v_d_over3.inputs, ["Scale"]))

    v_2d_over3 = vec_math("SCALE", (360, 260))
    _link(links, _find_socket(v_end_minus_p0.outputs, ["Vector"]), _find_socket(v_2d_over3.inputs, ["Vector"]))
    _link(links, two_third, _find_socket(v_2d_over3.inputs, ["Scale"]))

    h1_lin = vec_math("ADD", (560, 340))
    _link(links, p0, _find_socket(h1_lin.inputs, ["Vector"]))
    _link(links, _find_socket(v_d_over3.outputs, ["Vector"]), _find_socket(h1_lin.inputs, ["Vector_001"]))

    h2_lin = vec_math("ADD", (560, 260))
    _link(links, p0, _find_socket(h2_lin.inputs, ["Vector"]))
    _link(links, _find_socket(v_2d_over3.outputs, ["Vector"]), _find_socket(h2_lin.inputs, ["Vector_001"]))

    # Quadratic conversion using control P1 and end_pt
    v_p1_minus_p0 = vec_math("SUBTRACT", (160, 160))
    _link(links, p1, _find_socket(v_p1_minus_p0.inputs, ["Vector"]))
    _link(links, p0, _find_socket(v_p1_minus_p0.inputs, ["Vector_001"]))

    v_23_p1p0 = vec_math("SCALE", (360, 160))
    _link(links, _find_socket(v_p1_minus_p0.outputs, ["Vector"]), _find_socket(v_23_p1p0.inputs, ["Vector"]))
    _link(links, two_third, _find_socket(v_23_p1p0.inputs, ["Scale"]))

    h1_quad = vec_math("ADD", (560, 160))
    _link(links, p0, _find_socket(h1_quad.inputs, ["Vector"]))
    _link(links, _find_socket(v_23_p1p0.outputs, ["Vector"]), _find_socket(h1_quad.inputs, ["Vector_001"]))

    v_p1_minus_end = vec_math("SUBTRACT", (160, 60))
    _link(links, p1, _find_socket(v_p1_minus_end.inputs, ["Vector"]))
    _link(links, end_pt, _find_socket(v_p1_minus_end.inputs, ["Vector_001"]))

    v_23_p1e = vec_math("SCALE", (360, 60))
    _link(links, _find_socket(v_p1_minus_end.outputs, ["Vector"]), _find_socket(v_23_p1e.inputs, ["Vector"]))
    _link(links, two_third, _find_socket(v_23_p1e.inputs, ["Scale"]))

    h2_quad = vec_math("ADD", (560, 60))
    _link(links, end_pt, _find_socket(h2_quad.inputs, ["Vector"]))
    _link(links, _find_socket(v_23_p1e.outputs, ["Vector"]), _find_socket(h2_quad.inputs, ["Vector_001"]))

    # Choose between linear vs quadratic
    sw_h1_lin_quad = switch_vec((760, 170))
    _link(links, _find_socket(quad_enabled.outputs, ["Boolean"]), _find_socket(sw_h1_lin_quad.inputs, ["Switch"]))
    _link(links, _find_socket(h1_lin.outputs, ["Vector"]), _find_socket(sw_h1_lin_quad.inputs, ["False"]))
    _link(links, _find_socket(h1_quad.outputs, ["Vector"]), _find_socket(sw_h1_lin_quad.inputs, ["True"]))

    sw_h2_lin_quad = switch_vec((760, 70))
    _link(links, _find_socket(quad_enabled.outputs, ["Boolean"]), _find_socket(sw_h2_lin_quad.inputs, ["Switch"]))
    _link(links, _find_socket(h2_lin.outputs, ["Vector"]), _find_socket(sw_h2_lin_quad.inputs, ["False"]))
    _link(links, _find_socket(h2_quad.outputs, ["Vector"]), _find_socket(sw_h2_lin_quad.inputs, ["True"]))

    # If cubic enabled, override with p1/p2 handles
    sw_h1_final = switch_vec((940, 170))
    _link(links, use_p3, _find_socket(sw_h1_final.inputs, ["Switch"]))
    _link(links, _find_socket(sw_h1_lin_quad.outputs, ["Output"]), _find_socket(sw_h1_final.inputs, ["False"]))
    _link(links, p1, _find_socket(sw_h1_final.inputs, ["True"]))

    sw_h2_final = switch_vec((940, 70))
    _link(links, use_p3, _find_socket(sw_h2_final.inputs, ["Switch"]))
    _link(links, _find_socket(sw_h2_lin_quad.outputs, ["Output"]), _find_socket(sw_h2_final.inputs, ["False"]))
    _link(links, p2, _find_socket(sw_h2_final.inputs, ["True"]))

    h1_final = _find_socket(sw_h1_final.outputs, ["Output"])
    h2_final = _find_socket(sw_h2_final.outputs, ["Output"])

    # -----------------------------------------
    # Create Bezier Segment (always cubic)
    # -----------------------------------------
    bez = nodes.new("GeometryNodeCurvePrimitiveBezierSegment")
    bez.location = (1120, 120)

    _link(links, p0, _find_socket(bez.inputs, ["Start"]))
    _link(links, h1_final, _find_socket(bez.inputs, ["Start Handle"]))
    _link(links, h2_final, _find_socket(bez.inputs, ["End Handle"]))
    _link(links, end_pt, _find_socket(bez.inputs, ["End"]))

    if _find_socket(bez.inputs, ["Resolution"]) and "Resolution" in n_in.outputs:
        _link(links, n_in.outputs["Resolution"], _find_socket(bez.inputs, ["Resolution"]))

    _link(links, _find_socket(bez.outputs, ["Curve"]), n_out.inputs["Curve"])

    return ng


class NODE_OT_add_bezier_from_4_points_manual(bpy.types.Operator):
    bl_idname = "node.add_bezier_from_4_points_manual"
    bl_label = "Bezier From 4 Points"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.space_data.tree_type != "GeometryNodeTree":
            self.report({"ERROR"}, "Open a Geometry Nodes editor to add this node.")
            return {"CANCELLED"}

        ng = build_group()

        tree = context.space_data.edit_tree
        node = tree.nodes.new("GeometryNodeGroup")
        node.node_tree = ng
        node.label = GROUP_NAME
        node.location = getattr(context.space_data, "cursor_location", (0, 0))

        return {"FINISHED"}


def menu_func(self, context):
    if context.space_data.tree_type == "GeometryNodeTree":
        self.layout.operator(
            NODE_OT_add_bezier_from_4_points_manual.bl_idname,
            text="Bezier From 4 Points",
            icon="CURVE_BEZCURVE",
        )


classes = (NODE_OT_add_bezier_from_4_points_manual,)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.NODE_MT_add.append(menu_func)


def unregister():
    bpy.types.NODE_MT_add.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
