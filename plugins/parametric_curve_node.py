bl_info = {
    "name": "Parametric Curve",
    "author": "Alessio Fumagalli",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "Geometry Nodes > Add",
    "description": "Parametric curve primitive (x(t), y(t), z(t)) built from native Geometry Nodes",
    "category": "Node",
}

import bpy
from math import pi, e, tau

GROUP_NAME = "Parametric Curve"


# -----------------------------
# Utility: create a Value node
# -----------------------------
def make_value(nodes, val, loc=(0, 0)):
    n = nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = float(val)
    n.location = loc
    return n, n.outputs[0]


# --------------------------------------
# Shunting-yard tokenizer & parser (RPN)
# --------------------------------------
import re

_TOKEN_SPEC = [
    ("NUMBER", r"\d+(\.\d+)?"),  # 12, 12.34
    ("ID", r"[A-Za-z_]\w*"),  # identifiers
    ("OP", r"[\+\-\*/\^\(\),]"),  # operators and delimiters
    ("SKIP", r"[ \t]+"),  # spaces
]
_TOKEN_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _TOKEN_SPEC))


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


# Operator precedence & associativity
_PRECEDENCE = {
    "^": (4, "right"),
    "*": (3, "left"),
    "/": (3, "left"),
    "+": (2, "left"),
    "-": (2, "left"),
}

# function arity map (None = variadic handled elsewhere, here we use 1 or 2)
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


def to_rpn(expr):
    expr = expr.strip()
    if not expr:
        raise ValueError("Expression is empty")

    out = []
    stack = []
    arg_count = []  # for multi-arg functions

    prev_token = None
    for typ, txt in tokenize(expr):
        low = txt.lower()

        if typ == "NUMBER":
            out.append(("NUMBER", txt))
        elif typ == "ID":
            # treat all IDs as functions if followed by '(' (handled when '(' appears)
            out.append(("ID", txt)) if prev_token and prev_token[
                1
            ] == ")" else out.append(("ID", txt))  # placeholder
            # We handle real function detection when '(' is processed
            out[-1] = ("ID", txt)
        elif typ == "OP":
            if txt == "(":
                # If previous token was an ID => function call
                if prev_token and prev_token[0] == "ID":
                    stack.append(("FUNC", prev_token[1]))
                    # remove the identifier just put to output
                    out.pop()
                    arg_count.append(1)  # at least one argument by default
                stack.append(("OP", "("))
            elif txt == ",":
                # function argument separator
                while stack and not (stack[-1][0] == "OP" and stack[-1][1] == "("):
                    out.append(stack.pop())
                if not stack:
                    raise ValueError("Misplaced comma or mismatched parentheses")
                # bump arg counter
                if not arg_count:
                    raise ValueError("Comma outside of function call")
                arg_count[-1] += 1
            elif txt == ")":
                while stack and not (stack[-1][0] == "OP" and stack[-1][1] == "("):
                    out.append(stack.pop())
                if not stack:
                    raise ValueError("Mismatched parentheses")
                stack.pop()  # pop '('
                # if function at the top of the stack, output it with arity
                if stack and stack[-1][0] == "FUNC":
                    func = stack.pop()[1]
                    nargs = arg_count.pop() if arg_count else 1
                    out.append(("FUNC", func, nargs))
            else:
                # Check for unary minus/plus
                is_unary = (
                    prev_token is None
                    or (prev_token[0] == "OP" and prev_token[1] in ("(", "+", "-", "*", "/", "^", ","))
                )
                
                if is_unary and txt in ("-", "+"):
                    # Treat unary minus/plus as a unary operator
                    if txt == "-":
                        stack.append(("UNARY", "neg"))
                    # Unary plus does nothing, so we skip it
                else:
                    # binary operators
                    while stack:
                        top = stack[-1]
                        if top[0] == "OP" and top[1] in _PRECEDENCE:
                            p1, assoc1 = _PRECEDENCE[txt]
                            p2, _ = _PRECEDENCE[top[1]]
                            if (assoc1 == "left" and p1 <= p2) or (
                                assoc1 == "right" and p1 < p2
                            ):
                                out.append(stack.pop())
                            else:
                                break
                        elif top[0] == "UNARY":
                            # Unary operators have highest precedence
                            out.append(stack.pop())
                        else:
                            break
                    stack.append(("OP", txt))
        prev_token = (typ, txt)

    while stack:
        tok = stack.pop()
        if tok[0] == "OP" and tok[1] in ("(", ")"):
            raise ValueError("Mismatched parentheses at end")
        out.append(tok)
    return out


# ---------------------------------------------
# Build Math node graph from RPN into GN editor
# ---------------------------------------------
def make_math(nodes, op, a=None, b=None, loc=(0, 0)):
    # op is Blender Math operation enum name
    n = nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    if a is not None:
        nodes.id_data.links.new(a, n.inputs[0])
    if b is not None:
        nodes.id_data.links.new(b, n.inputs[1])
    return n, n.outputs[0]


def build_expr(nodes, base_x, base_y, source_socket_t, expr_string):
    """
    Returns (socket, rightmost_x) where socket is the output socket (Float field) of the expression.
    base_x/base_y define the layout origin for this expression column.
    """
    rpn = to_rpn(expr_string)
    stack = []
    x = base_x
    y = base_y
    dx = 220
    dy = -140

    def push_socket(s):
        nonlocal x, y
        stack.append((s, x, y))
        y += dy

    def pop2():
        b = stack.pop()[0]
        a = stack.pop()[0]
        return a, b

    for tok in rpn:
        if tok[0] == "NUMBER":
            node, sock = make_value(nodes, float(tok[1]), loc=(x, y))
            push_socket(sock)
            x += dx
        elif tok[0] == "ID":
            name = tok[1].lower()
            if name in ("t",):
                push_socket(source_socket_t)
                x += dx
            elif name in ("pi", "e", "tau"):
                val = {"pi": pi, "e": e, "tau": tau}[name]
                node, sock = make_value(nodes, val, loc=(x, y))
                push_socket(sock)
                x += dx
            else:
                raise ValueError(
                    f"Unknown identifier '{tok[1]}' (use t, pi, e, tau, or functions)"
                )
        elif tok[0] == "OP":
            op = tok[1]
            if op in {"+", "-", "*", "/", "^"}:
                a, b = pop2()
                if op == "+":
                    node, sock = make_math(nodes, "ADD", a, b, loc=(x, y))
                elif op == "-":
                    node, sock = make_math(nodes, "SUBTRACT", a, b, loc=(x, y))
                elif op == "*":
                    node, sock = make_math(nodes, "MULTIPLY", a, b, loc=(x, y))
                elif op == "/":
                    node, sock = make_math(nodes, "DIVIDE", a, b, loc=(x, y))
                elif op == "^":
                    node, sock = make_math(nodes, "POWER", a, b, loc=(x, y))
                push_socket(sock)
                x += dx
            else:
                raise ValueError(f"Unsupported operator '{op}'")
        elif tok[0] == "UNARY":
            # Handle unary operators
            op = tok[1]
            if op == "neg":
                a = stack.pop()[0]
                node, sock = make_math(nodes, "MULTIPLY", a, None, loc=(x, y))
                node.inputs[1].default_value = -1.0
                push_socket(sock)
                x += dx
            else:
                raise ValueError(f"Unsupported unary operator '{op}'")
        elif tok[0] == "FUNC":
            fname = tok[1].lower()
            nargs = tok[2]
            if fname in _FUNC_1 and nargs == 1:
                a = stack.pop()[0]
                opmap = {
                    "sin": "SINE",
                    "cos": "COSINE",
                    "tan": "TANGENT",
                    "asin": "ARCSINE",
                    "acos": "ARCCOSINE",
                    "atan": "ARCTANGENT",
                    "sqrt": "SQRT",
                    "abs": "ABSOLUTE",
                    "exp": "EXPONENT",
                    "ln": "LOGARITHM",
                    "floor": "FLOOR",
                    "ceil": "CEIL",
                    "frac": "FRACTION",
                }
                if fname == "ln":
                    # LOGARITHM with base e
                    node, sock = make_math(nodes, "LOGARITHM", a, None, loc=(x, y))
                    node.inputs[1].default_value = e
                else:
                    node, sock = make_math(nodes, opmap[fname], a, None, loc=(x, y))
                push_socket(sock)
                x += dx
            elif fname in _FUNC_2 and nargs == 2:
                b = stack.pop()[0]
                a = stack.pop()[0]
                if fname == "pow":
                    node, sock = make_math(nodes, "POWER", a, b, loc=(x, y))
                elif fname == "log":
                    node, sock = make_math(nodes, "LOGARITHM", a, b, loc=(x, y))
                elif fname == "min":
                    node, sock = make_math(nodes, "MINIMUM", a, b, loc=(x, y))
                elif fname == "max":
                    node, sock = make_math(nodes, "MAXIMUM", a, b, loc=(x, y))
                elif fname == "mod":
                    node, sock = make_math(nodes, "MODULO", a, b, loc=(x, y))
                else:
                    raise ValueError(f"Unsupported function '{fname}'")
                push_socket(sock)
                x += dx
            else:
                raise ValueError(
                    f"Function '{fname}' expects {1 if fname in _FUNC_1 else 2} argument(s)"
                )
        else:
            raise ValueError(f"Token not handled: {tok}")
    if len(stack) != 1:
        raise ValueError("Malformed expression (stack not singular at end)")
    return stack[0][0], x


# -------------------------------
# Interface socket helper
# -------------------------------
def ensure_socket(iface, name, in_out, socket_type, default=None, min_value=None, max_value=None):
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
    if min_value is not None and hasattr(sock, "min_value"):
        sock.min_value = min_value
    if max_value is not None and hasattr(sock, "max_value"):
        sock.max_value = max_value
    return sock


# -------------------------------
# Socket lookup helper
# -------------------------------
def first_geo_socket(sockets, preferred_names=()):
    # try preferred names first
    for name in preferred_names:
        if name in sockets:
            return sockets[name]
    # else first geometry-typed socket
    for s in sockets:
        if getattr(s, "bl_socket_idname", "").lower().endswith("geometry"):
            return s
    # fallback: first socket if nothing else
    return sockets[0] if sockets else None


# ---------------------------------------
# Build the whole node group from scratch
# ---------------------------------------
def build_group_from_expressions(x_expr, y_expr, z_expr):
    # make (or reuse) the GN group
    if GROUP_NAME in bpy.data.node_groups:
        ng = bpy.data.node_groups[GROUP_NAME]
        # wipe and rebuild nodes, but keep interface sockets
        ng.nodes.clear()
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")

    iface = ng.interface
    ensure_socket(iface, "Geometry", "OUTPUT", "NodeSocketGeometry")
    ensure_socket(iface, "t Min", "INPUT", "NodeSocketFloat", default=0.0)
    ensure_socket(iface, "t Max", "INPUT", "NodeSocketFloat", default=1.0)
    ensure_socket(iface, "Resolution", "INPUT", "NodeSocketInt", default=100, min_value=1)

    nodes = ng.nodes
    links = ng.links
    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-1200, 0)
    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (900, 0)

    # (1) Mesh Line (POINTS)
    n_line = nodes.new("GeometryNodeMeshLine")
    n_line.location = (-1000, 200)
    # Blender 5.0 enum is OFFSET/END_POINTS; POINTS was removed
    n_line.mode = "OFFSET"
    links.new(n_in.outputs["Resolution"], n_line.inputs["Count"])

    # (2) Index → t in [tMin, tMax]
    n_index = nodes.new("GeometryNodeInputIndex")
    n_index.location = (-1000, -180)

    n_res_minus = nodes.new("ShaderNodeMath")
    n_res_minus.operation = "SUBTRACT"
    n_res_minus.location = (-820, -260)
    links.new(n_in.outputs["Resolution"], n_res_minus.inputs[0])
    n_res_minus.inputs[1].default_value = 1.0

    n_div = nodes.new("ShaderNodeMath")
    n_div.operation = "DIVIDE"
    n_div.location = (-640, -260)
    links.new(n_index.outputs[0], n_div.inputs[0])
    links.new(n_res_minus.outputs[0], n_div.inputs[1])

    n_span = nodes.new("ShaderNodeMath")
    n_span.operation = "SUBTRACT"
    n_span.location = (-820, -80)
    links.new(n_in.outputs["t Max"], n_span.inputs[0])
    links.new(n_in.outputs["t Min"], n_span.inputs[1])

    n_t_scaled = nodes.new("ShaderNodeMath")
    n_t_scaled.operation = "MULTIPLY"
    n_t_scaled.location = (-640, -80)
    links.new(n_div.outputs[0], n_t_scaled.inputs[0])
    links.new(n_span.outputs[0], n_t_scaled.inputs[1])

    n_t = nodes.new("ShaderNodeMath")
    n_t.operation = "ADD"
    n_t.location = (-460, -80)
    links.new(n_in.outputs["t Min"], n_t.inputs[0])
    links.new(n_t_scaled.outputs[0], n_t.inputs[1])

    # (3) Build x(t), y(t), z(t) graphs
    try:
        x_sock, xr = build_expr(
            nodes,
            base_x=-280,
            base_y=240,
            source_socket_t=n_t.outputs[0],
            expr_string=x_expr,
        )
        y_sock, yr = build_expr(
            nodes,
            base_x=-280,
            base_y=60,
            source_socket_t=n_t.outputs[0],
            expr_string=y_expr,
        )
        z_sock, zr = build_expr(
            nodes,
            base_x=-280,
            base_y=-120,
            source_socket_t=n_t.outputs[0],
            expr_string=z_expr,
        )
    except Exception as ex:
        raise

    n_combine = nodes.new("ShaderNodeCombineXYZ")
    n_combine.location = (max(xr, yr, zr) + 60, 60)
    links.new(x_sock, n_combine.inputs[0])
    links.new(y_sock, n_combine.inputs[1])
    links.new(z_sock, n_combine.inputs[2])

    # (4) Points pipeline → Curve
    n_points = nodes.new("GeometryNodeMeshToPoints")
    n_points.location = (-820, 200)
    links.new(n_line.outputs["Mesh"], n_points.inputs["Mesh"])

    n_setpos = nodes.new("GeometryNodeSetPosition")
    n_setpos.location = (max(xr, yr, zr) + 260, 60)
    links.new(n_points.outputs["Points"], n_setpos.inputs["Geometry"])
    links.new(n_combine.outputs["Vector"], n_setpos.inputs["Position"])

    n_curve = nodes.new("GeometryNodePointsToCurves")
    n_curve.location = (max(xr, yr, zr) + 480, 60)
    links.new(n_setpos.outputs["Geometry"], n_curve.inputs["Points"])

    out_curve = first_geo_socket(
        n_curve.outputs, ("Curve Instances", "Curves", "Curve")
    )
    links.new(out_curve, n_out.inputs["Geometry"])

    return ng


# ---------------------------------------
# Operator: Add the GN group into the tree
# ---------------------------------------
class NODE_OT_add_parametric_curve_gn(bpy.types.Operator):
    bl_idname = "node.add_parametric_curve_gn"
    bl_label = "Parametric Curve"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Build a default helix initially so it renders immediately
        ng = build_group_from_expressions("cos(t)", "sin(t)", "t/(2*pi)")
        tree = context.space_data.edit_tree
        node = tree.nodes.new("GeometryNodeGroup")
        node.node_tree = ng
        node.label = GROUP_NAME
        node.location = getattr(context.space_data, "cursor_location", (0, 0))
        node["x_expr"] = "cos(t)"
        node["y_expr"] = "sin(t)"
        node["z_expr"] = "t/(2*pi)"

        # Auto-wire to root Group Output
        out = next((n for n in tree.nodes if n.bl_idname == "NodeGroupOutput"), None)
        if out and "Geometry" in out.inputs and "Geometry" in node.outputs:
            context.space_data.edit_tree.links.new(
                node.outputs["Geometry"], out.inputs["Geometry"]
            )
        return {"FINISHED"}


# ---------------------------------------
# Operator: (Re)build from expressions UI
# ---------------------------------------
class NODE_OT_build_parametric_curve(bpy.types.Operator):
    bl_idname = "node.build_parametric_curve_gn"
    bl_label = "Build Curve"
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
            self.report({"ERROR"}, "Select the 'Parametric Curve' node to build")
            return {"CANCELLED"}

        x_expr = node.get("x_expr", "cos(t)")
        y_expr = node.get("y_expr", "sin(t)")
        z_expr = node.get("z_expr", "t/(2*pi)")

        try:
            ng = build_group_from_expressions(x_expr, y_expr, z_expr)
        except Exception as ex:
            self.report({"ERROR"}, f"Parse/build error: {ex}")
            return {"CANCELLED"}

        node.node_tree = ng
        self.report({"INFO"}, "Parametric curve rebuilt")
        return {"FINISHED"}


# ---------------------------------------
# UI Panel in the GN editor N-panel
# ---------------------------------------
class NODE_PT_parametric_curve(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Parametric Curve"
    bl_label = "Parametric Curve"

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
        node = context.space_data.edit_tree.nodes.active
        col = layout.column(align=True)
        col.prop(node, '["x_expr"]', text="x(t)")
        col.prop(node, '["y_expr"]', text="y(t)")
        col.prop(node, '["z_expr"]', text="z(t)")
        layout.separator()
        layout.operator("node.build_parametric_curve_gn", icon="FILE_REFRESH")


# ---------------------------------------
# Menu hook + register
# ---------------------------------------
def menu_func(self, context):
    if context.space_data.tree_type == "GeometryNodeTree":
        self.layout.operator(
            NODE_OT_add_parametric_curve_gn.bl_idname,
            text="Parametric Curve",
            icon="CURVE_NCURVE",
        )


classes = (
    NODE_OT_add_parametric_curve_gn,
    NODE_OT_build_parametric_curve,
    NODE_PT_parametric_curve,
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
