bl_info = {
    "name": "Bezier C1 Connection Handles",
    "author": "Alessio Fumagalli",
    "version": (1, 4, 0),
    "blender": (5, 0, 0),
    "location": "Geometry Nodes > Add",
    "description": "Compute B Second as a point geometry from A End/A Prev for C1 continuation with degree toggles",
    "category": "Node",
}

import bpy
import random  # <<< ADDED (only for hidden random)

GROUP_NAME = "Bezier C1 Connection Handles"

# --- Hidden random (ADDED) ---
DEFAULT_DIGITS = 100
HIDDEN_PROP = "hidden_random"
DIGITS_PROP = "hidden_random_digits"
MIN_PROP = "hidden_random_min"
MAX_PROP = "hidden_random_max"


def rand_with_digits(digits: int) -> int:
    if not isinstance(digits, int) or digits < 1:
        raise ValueError("digits must be an integer >= 1")
    lo = 10 ** (digits - 1)
    hi = 10**digits - 1
    return random.randint(lo, hi)


def ensure_socket(iface, name, in_out, socket_type, default=None):
    sock = next(
        (
            s
            for s in iface.items_tree
            if s.name == name and getattr(s, "in_out", None) == in_out
        ),
        None,
    )
    if not sock:
        sock = iface.new_socket(name, socket_type=socket_type, in_out=in_out)

    if default is not None and hasattr(sock, "default_value"):
        sock.default_value = default
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
    if GROUP_NAME in bpy.data.node_groups:
        ng = bpy.data.node_groups[GROUP_NAME]
        ng.nodes.clear()
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")

    # --- Hidden random stored on node group (ADDED) ---
    # Stored as string to avoid precision/size issues for huge integers.
    digits = DEFAULT_DIGITS
    n = rand_with_digits(digits)
    ng[HIDDEN_PROP] = str(n)
    ng[DIGITS_PROP] = int(digits)
    ng[MIN_PROP] = str(10 ** (digits - 1))
    ng[MAX_PROP] = str(10**digits - 1)

    iface = ng.interface

    # Minimal interface requested: only two inputs and one output.
    ensure_socket(iface, "A End", "INPUT", "NodeSocketGeometry")
    ensure_socket(iface, "A Prev", "INPUT", "NodeSocketGeometry")
    ensure_socket(
        iface, "Input Is Cubic (Deg3)", "INPUT", "NodeSocketBool", default=False
    )
    ensure_socket(
        iface, "Output Is Cubic (Deg3)", "INPUT", "NodeSocketBool", default=False
    )
    ensure_socket(iface, "B Second", "OUTPUT", "NodeSocketGeometry")

    nodes = ng.nodes
    links = ng.links

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-900, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (380, 0)

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

    def switch_float(loc):
        n = nodes.new("GeometryNodeSwitch")
        n.location = loc
        n.input_type = "FLOAT"
        return n

    def sample_pos(label, geo_socket_name, loc):
        realize = nodes.new("GeometryNodeRealizeInstances")
        realize.location = (loc[0] - 230, loc[1])
        _link(
            links,
            n_in.outputs[geo_socket_name],
            _find_socket(realize.inputs, ["Geometry"]),
        )

        samp = nodes.new("GeometryNodeSampleIndex")
        samp.location = loc
        samp.data_type = "FLOAT_VECTOR"
        samp.domain = "POINT"

        _link(
            links,
            _find_socket(realize.outputs, ["Geometry"]),
            _find_socket(samp.inputs, ["Geometry"]),
        )

        idx0 = nodes.new("FunctionNodeInputInt")
        idx0.location = (loc[0] - 230, loc[1] - 130)
        idx0.integer = 0
        _link(
            links,
            _find_socket(idx0.outputs, ["Integer"]),
            _find_socket(samp.inputs, ["Index"]),
        )

        pos = nodes.new("GeometryNodeInputPosition")
        pos.location = (loc[0] - 200, loc[1] - 230)
        _link(links, pos.outputs["Position"], _find_socket(samp.inputs, ["Value"]))

        samp.label = label
        return _find_socket(samp.outputs, ["Value"])

    a_end = sample_pos("A End sample", "A End", (-600, 140))
    a_prev = sample_pos("A Prev sample", "A Prev", (-600, -80))

    # Tangent direction at the join from the previous Bezier side.
    # d_in = n_in * (A_end - A_prev), with n_in in {2, 3}
    v = vec_math("SUBTRACT", (-320, 40))
    _link(links, a_end, _find_socket(v.inputs, ["Vector"]))
    _link(links, a_prev, _find_socket(v.inputs, ["Vector_001"]))

    c2 = make_value(2.0, (-180, 170))
    c3 = make_value(3.0, (-180, 130))

    in_deg = switch_float((-20, 170))
    _link(
        links,
        n_in.outputs["Input Is Cubic (Deg3)"],
        _find_socket(in_deg.inputs, ["Switch"]),
    )
    _link(links, c2, _find_socket(in_deg.inputs, ["False"]))
    _link(links, c3, _find_socket(in_deg.inputs, ["True"]))

    out_deg = switch_float((-20, 80))
    _link(
        links,
        n_in.outputs["Output Is Cubic (Deg3)"],
        _find_socket(out_deg.inputs, ["Switch"]),
    )
    _link(links, c2, _find_socket(out_deg.inputs, ["False"]))
    _link(links, c3, _find_socket(out_deg.inputs, ["True"]))

    ratio = nodes.new("ShaderNodeMath")
    ratio.location = (140, 130)
    ratio.operation = "DIVIDE"
    _link(links, _find_socket(in_deg.outputs, ["Output"]), ratio.inputs[0])
    _link(links, _find_socket(out_deg.outputs, ["Output"]), ratio.inputs[1])

    # C1 gives Q1 = A_end + (n_in / n_out) * (A_end - A_prev)
    # We output B Second:
    # - deg2 output: B Second = Q1
    # - deg3 output: B Second = Q2 = A_end + 2*(Q1 - A_end)
    out_mul = switch_float((300, 80))
    _link(
        links,
        n_in.outputs["Output Is Cubic (Deg3)"],
        _find_socket(out_mul.inputs, ["Switch"]),
    )
    _link(links, make_value(1.0, (120, 40)), _find_socket(out_mul.inputs, ["False"]))
    _link(links, c2, _find_socket(out_mul.inputs, ["True"]))

    scale = nodes.new("ShaderNodeMath")
    scale.location = (480, 120)
    scale.operation = "MULTIPLY"
    _link(links, ratio.outputs[0], scale.inputs[0])
    _link(links, _find_socket(out_mul.outputs, ["Output"]), scale.inputs[1])

    v_scaled = vec_math("SCALE", (660, 40))
    _link(
        links,
        _find_socket(v.outputs, ["Vector"]),
        _find_socket(v_scaled.inputs, ["Vector"]),
    )
    _link(links, scale.outputs[0], _find_socket(v_scaled.inputs, ["Scale"]))

    b_second = vec_math("ADD", (840, 40))
    _link(links, a_end, _find_socket(b_second.inputs, ["Vector"]))
    _link(
        links,
        _find_socket(v_scaled.outputs, ["Vector"]),
        _find_socket(b_second.inputs, ["Vector_001"]),
    )

    p = nodes.new("GeometryNodeMeshLine")
    p.location = (1030, 90)
    p.inputs["Count"].default_value = 1
    p.inputs["Offset"].default_value = (0.0, 0.0, 0.0)

    set_p = nodes.new("GeometryNodeSetPosition")
    set_p.location = (1220, 40)
    _link(
        links,
        _find_socket(p.outputs, ["Mesh"]),
        _find_socket(set_p.inputs, ["Geometry"]),
    )
    _link(
        links,
        _find_socket(b_second.outputs, ["Vector"]),
        _find_socket(set_p.inputs, ["Position"]),
    )

    _link(links, _find_socket(set_p.outputs, ["Geometry"]), n_out.inputs["B Second"])

    return ng


class NODE_OT_add_bezier_c1_connection_handles(bpy.types.Operator):
    bl_idname = "node.add_bezier_c1_connection_handles"
    bl_label = "Bezier C1 Connection Handles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        space = getattr(context, "space_data", None)
        if space is None or getattr(space, "tree_type", None) != "GeometryNodeTree":
            self.report({"ERROR"}, "Open a Geometry Nodes editor to add this node.")
            return {"CANCELLED"}

        ng = build_group()

        tree = getattr(space, "edit_tree", None) or getattr(space, "node_tree", None)
        if tree is None:
            self.report(
                {"ERROR"},
                "No editable Geometry Node tree found. Open or create a node group first.",
            )
            return {"CANCELLED"}

        node = tree.nodes.new("GeometryNodeGroup")
        node.node_tree = ng
        node.label = GROUP_NAME
        node.location = getattr(space, "cursor_location", (0, 0))

        return {"FINISHED"}


def menu_func(self, context):
    if context.space_data.tree_type == "GeometryNodeTree":
        self.layout.operator(
            NODE_OT_add_bezier_c1_connection_handles.bl_idname,
            text="Bezier C1 Connection Handles",
            icon="IPO_BEZIER",
        )


classes = (NODE_OT_add_bezier_c1_connection_handles,)


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
