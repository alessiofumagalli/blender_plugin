bl_info = {
    "name": "Calculate Surface",
    "author": "Alessio Fumagalli",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "Geometry Nodes > Add",
    "description": "Calculate surface from parametric curve and transformation matrix",
    "category": "Node",
}

import bpy
import bmesh
from mathutils import Vector, Matrix
from math import pi, e, tau
import re

GROUP_NAME = "Calculate Surface"


# ==================== Expression Parser ====================
_TOKEN_SPEC = [
    ("NUMBER", r"\d+(\.\d+)?"),
    ("ID", r"[A-Za-z_]\w*"),
    ("OP", r"[\+\-\*/\^\(\),]"),
    ("SKIP", r"[ \t]+"),
]
_TOKEN_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _TOKEN_SPEC))

_PRECEDENCE = {
    "^": (4, "right"),
    "*": (3, "left"),
    "/": (3, "left"),
    "+": (2, "left"),
    "-": (2, "left"),
}

_FUNC_1 = {
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sqrt",
    "abs",
    "exp",
    "ln",
    "floor",
    "ceil",
    "frac",
}
_FUNC_2 = {"pow", "log", "min", "max", "mod"}


def tokenize(expr):
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m:
            raise ValueError(f"Unexpected character at {pos}: '{expr[pos]}'")
        typ = m.lastgroup
        txt = m.group()
        pos = m.end()
        if typ == "SKIP":
            continue
        yield (typ, txt)


def to_rpn(expr):
    expr = expr.strip()
    if not expr:
        raise ValueError("Expression is empty")

    out = []
    stack = []
    arg_count = []

    prev_token = None
    for typ, txt in tokenize(expr):
        if typ == "NUMBER":
            out.append(("NUMBER", txt))
        elif typ == "ID":
            out.append(("ID", txt))
        elif typ == "OP":
            if txt == "(":
                if prev_token and prev_token[0] == "ID":
                    stack.append(("FUNC", prev_token[1]))
                    out.pop()
                    arg_count.append(1)
                stack.append(("OP", "("))
            elif txt == ",":
                while stack and not (stack[-1][0] == "OP" and stack[-1][1] == "("):
                    out.append(stack.pop())
                if arg_count:
                    arg_count[-1] += 1
            elif txt == ")":
                while stack and not (stack[-1][0] == "OP" and stack[-1][1] == "("):
                    out.append(stack.pop())
                if stack:
                    stack.pop()
                if stack and stack[-1][0] == "FUNC":
                    func = stack.pop()[1]
                    nargs = arg_count.pop() if arg_count else 1
                    out.append(("FUNC", func, nargs))
            else:
                is_unary = prev_token is None or (
                    prev_token[0] == "OP"
                    and prev_token[1] in ("(", "+", "-", "*", "/", "^", ",")
                )
                if is_unary and txt in ("-", "+"):
                    if txt == "-":
                        stack.append(("UNARY", "neg"))
                else:
                    while stack:
                        top = stack[-1]
                        if top[0] == "OP":
                            top_prec, top_assoc = _PRECEDENCE.get(top[1], (0, "left"))
                            txt_prec, txt_assoc = _PRECEDENCE.get(txt, (0, "left"))
                            if (txt_assoc == "left" and top_prec >= txt_prec) or (
                                txt_assoc == "right" and top_prec > txt_prec
                            ):
                                out.append(stack.pop())
                            else:
                                break
                        else:
                            break
                    stack.append(("OP", txt))
        prev_token = (typ, txt)

    while stack:
        out.append(stack.pop())
    return out


def eval_rpn(rpn, variables):
    """Evaluate RPN expression"""
    import math

    stack = []
    for tok in rpn:
        if tok[0] == "NUMBER":
            stack.append(float(tok[1]))
        elif tok[0] == "ID":
            var_name = tok[1].lower()
            if var_name in variables:
                stack.append(variables[var_name])
            elif var_name == "pi":
                stack.append(pi)
            elif var_name == "e":
                stack.append(e)
            elif var_name == "tau":
                stack.append(tau)
            else:
                raise ValueError(f"Unknown variable: {var_name}")
        elif tok[0] == "OP":
            op = tok[1]
            b = stack.pop()
            a = stack.pop()
            if op == "+":
                stack.append(a + b)
            elif op == "-":
                stack.append(a - b)
            elif op == "*":
                stack.append(a * b)
            elif op == "/":
                stack.append(a / b if b != 0 else 0)
            elif op == "^":
                stack.append(a**b)
        elif tok[0] == "UNARY":
            stack.append(-stack.pop())
        elif tok[0] == "FUNC":
            fname = tok[1].lower()
            nargs = tok[2] if len(tok) > 2 else 1
            if nargs == 1:
                arg = stack.pop()
                if fname == "sin":
                    stack.append(math.sin(arg))
                elif fname == "cos":
                    stack.append(math.cos(arg))
                elif fname == "tan":
                    stack.append(math.tan(arg))
                elif fname == "asin":
                    stack.append(math.asin(arg))
                elif fname == "acos":
                    stack.append(math.acos(arg))
                elif fname == "atan":
                    stack.append(math.atan(arg))
                elif fname == "sqrt":
                    stack.append(math.sqrt(arg))
                elif fname == "abs":
                    stack.append(abs(arg))
                elif fname == "exp":
                    stack.append(math.exp(arg))
                elif fname == "ln":
                    stack.append(math.log(arg))
                elif fname == "floor":
                    stack.append(math.floor(arg))
                elif fname == "ceil":
                    stack.append(math.ceil(arg))
                elif fname == "frac":
                    stack.append(arg - math.floor(arg))
            elif nargs == 2:
                b = stack.pop()
                a = stack.pop()
                if fname == "pow":
                    stack.append(a**b)
                elif fname == "log":
                    stack.append(math.log(a, b))
                elif fname == "min":
                    stack.append(min(a, b))
                elif fname == "max":
                    stack.append(max(a, b))
                elif fname == "mod":
                    stack.append(a % b)
    return stack[0] if stack else 0


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


def build_group():
    if GROUP_NAME in bpy.data.node_groups:
        ng = bpy.data.node_groups[GROUP_NAME]
        ng.nodes.clear()
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")

    iface = ng.interface
    ensure_socket(iface, "Geometry", "OUTPUT", "NodeSocketGeometry")
    ensure_socket(iface, "Curve Geometry", "INPUT", "NodeSocketGeometry")
    ensure_socket(iface, "Matrix", "INPUT", "NodeSocketMatrix")
    ensure_socket(iface, "s Min", "INPUT", "NodeSocketFloat", 0.0)
    ensure_socket(iface, "s Max", "INPUT", "NodeSocketFloat", 1.0)
    ensure_socket(iface, "Resolution", "INPUT", "NodeSocketInt", 32)

    nodes = ng.nodes
    links = ng.links

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (0, 0)
    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (500, 0)

    # Pass through curve geometry
    links.new(n_in.outputs["Curve Geometry"], n_out.inputs["Geometry"])

    return ng


class NODE_OT_add_calculate_surface_gn(bpy.types.Operator):
    bl_idname = "node.add_calculate_surface_gn"
    bl_label = "Calculate Surface"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ng = build_group()
        tree = context.space_data.edit_tree
        node = tree.nodes.new("GeometryNodeGroup")
        node.node_tree = ng
        node.label = GROUP_NAME
        node.location = getattr(context.space_data, "cursor_location", (0, 0))

        # Auto-wire to root Group Output
        out = next((n for n in tree.nodes if n.bl_idname == "NodeGroupOutput"), None)
        if out and "Geometry" in out.inputs and "Geometry" in node.outputs:
            tree.links.new(node.outputs["Geometry"], out.inputs["Geometry"])

        return {"FINISHED"}


class GEOMETRY_OT_calculate_surface(bpy.types.Operator):
    bl_idname = "geometry.build_calculate_surface"
    bl_label = "Build Surface"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tree = context.space_data.edit_tree
        node = tree.nodes.active

        if (
            not node
            or node.bl_idname != "GeometryNodeGroup"
            or not node.node_tree
            or node.node_tree.name != GROUP_NAME
        ):
            self.report({"ERROR"}, "Select the 'Calculate Surface' node")
            return {"CANCELLED"}

        # Find connected Curve node
        curve_node = None
        if "Curve Geometry" in node.inputs:
            for link in tree.links:
                if link.to_socket == node.inputs["Curve Geometry"]:
                    source_node = link.from_node
                    if (
                        source_node.bl_idname == "GeometryNodeGroup"
                        and source_node.node_tree
                    ):
                        if source_node.node_tree.name == "Parametric Curve":
                            curve_node = source_node
                            break

        if not curve_node:
            self.report({"ERROR"}, "Connect a Parametric Curve to Curve Geometry input")
            return {"CANCELLED"}

        # Find connected Matrix node
        matrix_node = None
        if "Matrix" in node.inputs:
            for link in tree.links:
                if link.to_socket == node.inputs["Matrix"]:
                    source_node = link.from_node
                    if (
                        source_node.bl_idname == "GeometryNodeGroup"
                        and source_node.node_tree
                    ):
                        if (
                            source_node.node_tree.name
                            == "Parametric Transformation Matrix"
                        ):
                            matrix_node = source_node
                            break

        if not matrix_node:
            self.report(
                {"ERROR"}, "Connect a Parametric Transformation Matrix to Matrix input"
            )
            return {"CANCELLED"}

        # Extract expressions
        x_expr = curve_node.get("x_expr", "cos(t)")
        y_expr = curve_node.get("y_expr", "sin(t)")
        z_expr = curve_node.get("z_expr", "t/(2*pi)")

        # Get t range from curve node inputs
        t_min = (
            curve_node.inputs["t Min"].default_value
            if "t Min" in curve_node.inputs
            else 0.0
        )
        t_max = (
            curve_node.inputs["t Max"].default_value
            if "t Max" in curve_node.inputs
            else 1.0
        )

        m_exprs = {}
        for i in range(16):
            key = f"m{i // 4}{i % 4}"
            m_exprs[key] = matrix_node.get(key, "1" if i % 5 == 0 else "0")

        # Get parameters from node inputs
        s_min = node.inputs["s Min"].default_value if "s Min" in node.inputs else 0.0
        s_max = node.inputs["s Max"].default_value if "s Max" in node.inputs else 1.0
        resolution = (
            int(node.inputs["Resolution"].default_value)
            if "Resolution" in node.inputs
            else 32
        )
        sweep_count = 50  # Fixed for now

        try:
            # Parse expressions
            x_rpn = to_rpn(x_expr)
            y_rpn = to_rpn(y_expr)
            z_rpn = to_rpn(z_expr)

            m_rpn = {}
            for key, expr in m_exprs.items():
                m_rpn[key] = to_rpn(expr)

            # Create unique name for this node's surface
            obj_name = f"Surface_{node.name}"

            # Remove old object if exists
            if obj_name in bpy.data.objects:
                old_obj = bpy.data.objects[obj_name]
                bpy.data.objects.remove(old_obj, do_unlink=True)

            # Create surface mesh
            mesh_data = bpy.data.meshes.new(obj_name + "_mesh")
            mesh_obj = bpy.data.objects.new(obj_name, mesh_data)
            context.collection.objects.link(mesh_obj)

            # Create mesh with bmesh
            bm = bmesh.new()
            vertices = []

            for s_idx in range(sweep_count):
                # Map s_idx to [s_min, s_max]
                s = s_min + (s_idx / max(1, sweep_count - 1)) * (s_max - s_min)
                row_verts = []

                for t_idx in range(resolution):
                    # Map t_idx to [t_min, t_max]
                    t = (
                        t_min + (t_idx / max(1, resolution - 1)) * (t_max - t_min)
                        if resolution > 1
                        else t_min
                    )

                    # Evaluate curve at t
                    x = eval_rpn(x_rpn, {"t": t})
                    y = eval_rpn(y_rpn, {"t": t})
                    z = eval_rpn(z_rpn, {"t": t})

                    # Get matrix at s
                    matrix_vals = {}
                    for key, rpn in m_rpn.items():
                        matrix_vals[key] = eval_rpn(rpn, {"s": s})

                    # Build 4x4 matrix - Blender uses row-major indexing
                    # but Matrix() constructor expects rows, so m[row][col]
                    m = Matrix(
                        [
                            [
                                matrix_vals.get("m00", 0),
                                matrix_vals.get("m01", 0),
                                matrix_vals.get("m02", 0),
                                matrix_vals.get("m03", 0),
                            ],
                            [
                                matrix_vals.get("m10", 0),
                                matrix_vals.get("m11", 0),
                                matrix_vals.get("m12", 0),
                                matrix_vals.get("m13", 0),
                            ],
                            [
                                matrix_vals.get("m20", 0),
                                matrix_vals.get("m21", 0),
                                matrix_vals.get("m22", 0),
                                matrix_vals.get("m23", 0),
                            ],
                            [
                                matrix_vals.get("m30", 0),
                                matrix_vals.get("m31", 0),
                                matrix_vals.get("m32", 0),
                                matrix_vals.get("m33", 1),
                            ],
                        ]
                    )

                    # Transform point
                    p = Vector([x, y, z, 1])
                    p_transformed = m @ p

                    # Create vertex
                    if p_transformed.w != 0:
                        v = bm.verts.new(
                            (
                                p_transformed.x / p_transformed.w,
                                p_transformed.y / p_transformed.w,
                                p_transformed.z / p_transformed.w,
                            )
                        )
                    else:
                        v = bm.verts.new(
                            (p_transformed.x, p_transformed.y, p_transformed.z)
                        )

                    row_verts.append(v)

                vertices.append(row_verts)

            # Create quad faces
            for s_idx in range(sweep_count - 1):
                for t_idx in range(resolution - 1):
                    v1 = vertices[s_idx][t_idx]
                    v2 = vertices[s_idx][t_idx + 1]
                    v3 = vertices[s_idx + 1][t_idx + 1]
                    v4 = vertices[s_idx + 1][t_idx]
                    try:
                        bm.faces.new([v1, v2, v3, v4])
                    except:
                        pass

            bm.to_mesh(mesh_data)
            bm.free()
            mesh_data.update()

            context.view_layer.objects.active = mesh_obj
            mesh_obj.select_set(True)

            self.report({"INFO"}, f"Surface created: {sweep_count}x{resolution} grid")
            return {"FINISHED"}

        except Exception as ex:
            self.report({"ERROR"}, f"Error: {str(ex)}")
            import traceback

            traceback.print_exc()
            return {"CANCELLED"}


class NODE_PT_calculate_surface(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Calculate Surface"
    bl_label = "Calculate Surface"

    @classmethod
    def poll(cls, context):
        tree = getattr(context.space_data, "edit_tree", None)
        node = getattr(tree, "nodes", None)
        node = tree.nodes.active if tree else None
        return bool(
            node
            and node.bl_idname == "GeometryNodeGroup"
            and node.node_tree
            and node.node_tree.name == GROUP_NAME
        )

    def draw(self, context):
        layout = self.layout
        layout.operator("geometry.build_calculate_surface", icon="MESH_DATA")


def menu_func(self, context):
    if context.space_data and context.space_data.tree_type == "GeometryNodeTree":
        self.layout.operator(
            NODE_OT_add_calculate_surface_gn.bl_idname, text="Calculate Surface"
        )


classes = (
    NODE_OT_add_calculate_surface_gn,
    GEOMETRY_OT_calculate_surface,
    NODE_PT_calculate_surface,
)


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
