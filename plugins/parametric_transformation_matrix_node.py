bl_info = {
    "name": "Parametric Transformation Matrix",
    "author": "Alessio Fumagalli",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "Geometry Nodes > Add",
    "description": "Parametric transformation matrix (4x4 homogeneous coordinates) built from native Geometry Nodes",
    "category": "Node",
}

import bpy
from math import pi, e, tau

GROUP_NAME = "Parametric Transformation Matrix"


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

# function arity map
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
                is_unary = prev_token is None or (
                    prev_token[0] == "OP"
                    and prev_token[1] in ("(", "+", "-", "*", "/", "^", ",")
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


def build_expr(nodes, base_x, base_y, source_socket_s, expr_string):
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
            if name == "s":
                push_socket(source_socket_s)
                x += dx
            elif name in ("pi", "e", "tau"):
                val = {"pi": pi, "e": e, "tau": tau}[name]
                node, sock = make_value(nodes, val, loc=(x, y))
                push_socket(sock)
                x += dx
            else:
                raise ValueError(
                    f"Unknown identifier '{tok[1]}' (use s, pi, e, tau, or functions)"
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
def ensure_socket(
    iface, name, in_out, socket_type, default=None, min_value=None, max_value=None
):
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
# A 4x4 transformation matrix in homogeneous coordinates:
# [m00 m01 m02 m03]
# [m10 m11 m12 m13]
# [m20 m21 m22 m23]
# [m30 m31 m32 m33]
# Where m3j are typically [0, 0, 0, 1] for affine transformations
# The node outputs a 4x4 matrix that can be applied to geometry
# When applied to a curve parameterized by t, it sweeps it out with varying (u,v)
# ---------------------------------------
def build_group_from_expressions(
    m00_expr,
    m01_expr,
    m02_expr,
    m03_expr,
    m10_expr,
    m11_expr,
    m12_expr,
    m13_expr,
    m20_expr,
    m21_expr,
    m22_expr,
    m23_expr,
    m30_expr,
    m31_expr,
    m32_expr,
    m33_expr,
):
    # make (or reuse) the GN group
    if GROUP_NAME in bpy.data.node_groups:
        ng = bpy.data.node_groups[GROUP_NAME]
        # wipe and rebuild nodes, but keep interface sockets
        ng.nodes.clear()
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")

    iface = ng.interface
    # Only output the Matrix socket, no geometry output
    ensure_socket(iface, "Matrix", "OUTPUT", "NodeSocketMatrix")
    ensure_socket(iface, "s", "INPUT", "NodeSocketFloat", default=0.0)

    nodes = ng.nodes
    links = ng.links

    # Create fresh input/output nodes
    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-2000, 0)
    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (2500, 0)

    # Get the s parameter socket from the newly created input node
    s_sock = n_in.outputs["s"]

    # (2) Build all 16 matrix entry expressions
    max_x = -1800
    try:
        exprs_list = [
            (m00_expr, -1000, 1200),  # row 0
            (m01_expr, -1000, 1000),
            (m02_expr, -1000, 800),
            (m03_expr, -1000, 600),
            (m10_expr, -1000, 300),  # row 1
            (m11_expr, -1000, 100),
            (m12_expr, -1000, -100),
            (m13_expr, -1000, -300),
            (m20_expr, -1000, -600),  # row 2
            (m21_expr, -1000, -800),
            (m22_expr, -1000, -1000),
            (m23_expr, -1000, -1200),
            (m30_expr, -1000, -1500),  # row 3 (usually [0, 0, 0, 1])
            (m31_expr, -1000, -1700),
            (m32_expr, -1000, -1900),
            (m33_expr, -1000, -2100),
        ]

        socks = []
        for expr, base_x, base_y in exprs_list:
            sock, rx = build_expr(
                nodes,
                base_x=base_x,
                base_y=base_y,
                source_socket_s=s_sock,
                expr_string=expr,
            )
            socks.append(sock)
            max_x = max(max_x, rx)
    except Exception as ex:
        raise

    # (3) Create a Combine Matrix node to merge all 16 values into a single matrix
    combine_matrix = nodes.new("FunctionNodeCombineMatrix")
    combine_matrix.location = (max_x + 120, 600)

    # Connect all 16 sockets to the Combine Matrix node inputs
    # Blender uses column-major order for matrices:
    # Input 0-3: Column 0 (m00, m10, m20, m30)
    # Input 4-7: Column 1 (m01, m11, m21, m31)
    # Input 8-11: Column 2 (m02, m12, m22, m32)
    # Input 12-15: Column 3 (m03, m13, m23, m33)
    # So we need to transpose the row-major socks list to column-major
    transposed_socks = []
    for col in range(4):
        for row in range(4):
            idx = row * 4 + col
            if idx < len(socks):
                transposed_socks.append(socks[idx])

    for i, sock in enumerate(transposed_socks):
        if i < len(combine_matrix.inputs):
            links.new(sock, combine_matrix.inputs[i])

    # (4) Connect the combined matrix to the output
    if "Matrix" in n_out.inputs and len(combine_matrix.outputs) > 0:
        links.new(combine_matrix.outputs[0], n_out.inputs["Matrix"])

    return ng


# ---------------------------------------
# Operator: Add the GN group into the tree
# ---------------------------------------
class NODE_OT_add_parametric_transformation_matrix_gn(bpy.types.Operator):
    bl_idname = "node.add_parametric_transformation_matrix_gn"
    bl_label = "Parametric Transformation Matrix"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Build a default translation matrix based on s
        # Translates along X axis based on parameter s
        ng = build_group_from_expressions(
            "1",
            "0",
            "0",
            "s",
            "0",
            "1",
            "0",
            "0",
            "0",
            "0",
            "1",
            "0",
            "0",
            "0",
            "0",
            "1",
        )
        tree = context.space_data.edit_tree
        node = tree.nodes.new("GeometryNodeGroup")
        node.node_tree = ng
        node.label = GROUP_NAME
        node.location = getattr(context.space_data, "cursor_location", (0, 0))

        # Store matrix expressions
        node["m00"] = "1"
        node["m01"] = "0"
        node["m02"] = "0"
        node["m03"] = "s"
        node["m10"] = "0"
        node["m11"] = "1"
        node["m12"] = "0"
        node["m13"] = "0"
        node["m20"] = "0"
        node["m21"] = "0"
        node["m22"] = "1"
        node["m23"] = "0"
        node["m30"] = "0"
        node["m31"] = "0"
        node["m32"] = "0"
        node["m33"] = "1"

        return {"FINISHED"}


# ---------------------------------------
# Operator: (Re)build from expressions UI
# ---------------------------------------
class NODE_OT_build_parametric_transformation_matrix(bpy.types.Operator):
    bl_idname = "node.build_parametric_transformation_matrix_gn"
    bl_label = "Build Transformation Matrix"
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
            self.report(
                {"ERROR"}, "Select the 'Parametric Transformation Matrix' node to build"
            )
            return {"CANCELLED"}

        # Retrieve all 16 matrix entries
        m_entries = []
        for i in range(16):
            key = f"m{i // 4}{i % 4}"
            default_val = "1" if i % 5 == 0 else "0"  # identity matrix default
            m_entries.append(node.get(key, default_val))

        try:
            ng = build_group_from_expressions(*m_entries)
        except Exception as ex:
            self.report({"ERROR"}, f"Parse/build error: {ex}")
            return {"CANCELLED"}

        node.node_tree = ng
        self.report({"INFO"}, "Parametric transformation matrix rebuilt")
        return {"FINISHED"}


# ---------------------------------------
# UI Panel in the GN editor N-panel
# ---------------------------------------
class NODE_PT_parametric_transformation_matrix(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Parametric Transformation Matrix"
    bl_label = "Parametric Transformation Matrix"

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

        # Draw the 4x4 matrix in a readable grid format
        layout.label(text="Transformation Matrix (4x4)")

        for row in range(4):
            row_box = layout.box()
            row_layout = row_box.row(align=True)
            for col in range(4):
                key = f"m{row}{col}"
                row_layout.prop(node, f'["{key}"]', text="")

        layout.separator()
        layout.operator(
            "node.build_parametric_transformation_matrix_gn", icon="FILE_REFRESH"
        )


# ---------------------------------------
# Menu hook + register
# ---------------------------------------
def menu_func(self, context):
    if context.space_data.tree_type == "GeometryNodeTree":
        self.layout.operator(
            NODE_OT_add_parametric_transformation_matrix_gn.bl_idname,
            text="Parametric Transformation Matrix",
            icon="EMPTY_AXIS",
        )


classes = (
    NODE_OT_add_parametric_transformation_matrix_gn,
    NODE_OT_build_parametric_transformation_matrix,
    NODE_PT_parametric_transformation_matrix,
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
