# Blender Parametric Geometry Plugins

This repository contains custom Blender plugins for creating parametric curves, surfaces, and transformations using Geometry Nodes.

## Contents

The repository includes four plugins:

### 1. **Parametric Curve Node** (`plugins/parametric_curve_node.py`)

Creates parametric curves defined by mathematical expressions x(t), y(t), z(t).

**Features:**
- Define curve equations using mathematical expressions
- Supports operators: `+`, `-`, `*`, `/`, `^` (power)
- Supports functions: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `sqrt`, `abs`, `exp`, `ln`, `floor`, `ceil`, `frac`, `pow`, `log`, `min`, `max`, `mod`
- Constants: `pi`, `e`, `tau`
- Adjustable parameter range (t Min, t Max) and resolution

**Usage:**
1. In Geometry Nodes editor: `Add > Parametric Curve`
2. Default generates a helix: `x = cos(t)`, `y = sin(t)`, `z = t/(2*pi)`
3. Select the node and press **N** to open side panel
4. Go to **"Parametric Curve"** tab
5. Edit expressions for x(t), y(t), z(t)
6. Click **"Build Curve"** to apply changes
7. Adjust t Min, t Max, and Resolution in node inputs

**Output:**
- `Geometry`: The generated curve

### 2. **Parametric Transformation Matrix Node** (`plugins/parametric_transformation_matrix_node.py`)

Creates 4x4 transformation matrices with entries defined by mathematical expressions that depend on parameter `s`.

**Features:**
- Define all 16 matrix entries m[i][j](s) as mathematical expressions
- Same mathematical operations and functions as Parametric Curve
- Parameter `s` for creating animated/swept transformations
- Homogeneous coordinates support (4x4 matrices)

**Usage:**
1. In Geometry Nodes editor: `Add > Parametric Transformation Matrix`
2. Default generates a translation matrix: identity with m03 = s
3. Select the node and press **N** to open side panel
4. Go to **"Parametric Transformation Matrix"** tab
5. Edit expressions for each matrix entry m00 through m33
6. Click **"Build Transformation Matrix"** to apply changes
7. Adjust parameter `s` in node input to preview at specific value

**Output:**
- `Matrix`: The 4x4 transformation matrix

**Example matrices:**
- Translation: `m03 = s`, others identity
- Rotation: `m00 = cos(s*2*pi)`, `m01 = -sin(s*2*pi)`, `m10 = sin(s*2*pi)`, `m11 = cos(s*2*pi)`
- Scaling: `m00 = 1+s`, `m11 = 1+s`, `m22 = 1+s`

### 3. **Calculate Surface Node** (`plugins/calculate_surface_node.py`)

Applies a parametric transformation matrix to a parametric curve over a range of values to generate a mesh surface.

**Features:**
- Combines Parametric Curve and Parametric Transformation Matrix
- Sweeps curve through transformation matrix parameter range
- Creates quad mesh surface with proper topology
- Configurable sweep range (s Min, s Max) and resolution

**Usage:**
1. First add and configure:
   - A **Parametric Curve** node (defines the base curve)
   - A **Parametric Transformation Matrix** node (defines how to transform it)
2. In Geometry Nodes editor: `Add > Calculate Surface`
3. Connect nodes:
   - `Parametric Curve.Geometry` → `Calculate Surface.Curve Geometry`
   - `Parametric Transformation Matrix.Matrix` → `Calculate Surface.Matrix`
4. Configure inputs:
   - `s Min`: Starting value for transformation parameter (default 0.0)
   - `s Max`: Ending value for transformation parameter (default 1.0)
   - `Resolution`: Number of points along curve (default 32)
5. Select the Calculate Surface node
6. Press **N** and go to **"Calculate Surface"** tab
7. Click **"Build Surface"** button

**Output:**
- `Geometry`: Pass-through of input curve (for preview)
- Creates a new mesh object `Surface_[NodeName]` in the scene with the calculated surface

**How it works:**
- Evaluates the curve at t ∈ [t_min, t_max] with `Resolution` points
- Evaluates the matrix at 50 steps of s ∈ [s_min, s_max]
- For each s value: transforms all curve points by M(s)
- Creates a quad mesh from the transformed points (50 × Resolution grid)

**Example workflow:**
```
Circle curve + Translation matrix → Cylinder
Helix curve + Rotation matrix → Twisted surface
Line curve + Scaling matrix → Cone
```

### 4. **Parametric Surface Node** (`plugins/parametric_surface_node.py`)

Creates parametric surfaces directly from equations x(u,v), y(u,v), z(u,v).

**Features:**
- Direct surface generation from two-parameter equations
- Uses parameters u and v
- Independent from curve/matrix system
- Same mathematical operations as other nodes

**Usage:**
1. In Geometry Nodes editor: `Add > Parametric Surface`
2. Select the node and press **N**
3. Edit expressions for x(u,v), y(u,v), z(u,v)
4. Click **"Build Surface"**

**Output:**
- `Geometry`: The generated surface mesh

**Note:** This is a standalone surface generator, separate from the curve transformation system.

## Installation

1. Open Blender 5.0 or later
2. Go to **Edit → Preferences**
3. Navigate to the **Add-ons** section
4. Click the down arrow (▼) in the top right corner
5. Select **Install from Disk**
6. Navigate to the `plugins/` folder
7. Select the Python plugin file(s) you want to install
8. Enable each plugin by checking the checkbox next to its name

**Tip:** Install all four plugins to access the complete parametric geometry system.

## Mathematical Expression Syntax

All nodes use the same expression parser:

**Operators:** `+`, `-`, `*`, `/`, `^` (power)

**Functions (1 argument):**
- Trigonometric: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`
- Math: `sqrt`, `abs`, `exp`, `ln`, `floor`, `ceil`, `frac`

**Functions (2 arguments):**
- `pow(a, b)`: a raised to power b
- `log(a, b)`: logarithm of a base b
- `min(a, b)`, `max(a, b)`: minimum/maximum
- `mod(a, b)`: modulo operation

**Constants:** `pi` (π), `e`, `tau` (2π)

**Variables:**
- Parametric Curve: `t`
- Parametric Surface: `u`, `v`
- Parametric Transformation Matrix: `s`

**Examples:**
- `cos(t) * sin(t)`
- `2 * pi * t`
- `sqrt(u^2 + v^2)`
- `sin(s * 2 * pi)`

## Workflow Examples

### Example 1: Create a Cylinder
1. Add Parametric Curve: `x = cos(t)`, `y = sin(t)`, `z = 0` (circle)
2. Set t range: 0 to 2*pi
3. Add Parametric Transformation Matrix: `m03 = s`, `m23 = s` (translation in X and Z)
4. Add Calculate Surface, connect both nodes
5. Set s range: 0 to 5
6. Build Surface → Creates cylinder

### Example 2: Create a Twisted Surface
1. Add Parametric Curve: `x = cos(t)`, `y = sin(t)`, `z = 0` (circle)
2. Add Parametric Transformation Matrix: rotation + translation
   - `m00 = cos(s*pi)`, `m01 = -sin(s*pi)`
   - `m10 = sin(s*pi)`, `m11 = cos(s*pi)`
   - `m23 = s*5` (move up as it rotates)
3. Add Calculate Surface and build
4. Result: Twisted tube

### Example 3: Create a Cone
1. Add Parametric Curve: `x = cos(t)`, `y = sin(t)`, `z = 0` (circle)
2. Add Parametric Transformation Matrix: scale down + translate
   - `m00 = 1-s`, `m11 = 1-s`, `m22 = 1` (shrink in X,Y)
   - `m23 = s*3` (move up)
3. Add Calculate Surface and build
4. Result: Cone

## Compatibility

These plugins are tested for **Blender v 5.0 and later**.

For more information about Blender, visit [https://www.blender.org](https://www.blender.org)

## Contributing

All contributions to this repository must be made through pull requests to the `main` branch. See [.github/BRANCH_PROTECTION_SETUP.md](.github/BRANCH_PROTECTION_SETUP.md) for details on configuring branch protection rules to enforce this workflow.

## License

See the [LICENSE](LICENSE) file for details.
