# Blender Parametric Geometry Plugins

This repository contains custom Blender plugins for creating parametric curves and surfaces using Geometry Nodes.

## Contents

The repository includes two plugins:

1. **Parametric Curve Node** (`plugins/parametric_curve_node.py`)
   - Creates parametric curves defined by equations x(t), y(t), z(t)
   - By default, generates a cylindrical helix
   - Allows customization of parametric equations through the node interface

2. **Parametric Surface Node** (`plugins/parametric_surface_node.py`)
   - Creates parametric surfaces defined by equations x(u,v), y(u,v), z(u,v)
   - Provides flexible surface generation based on mathematical functions

## Installation

1. Open Blender
2. Go to **Edit → Preferences**
3. Navigate to the **Add-ons** section
4. Click the down arrow icon in the top right corner
5. Select **Install from Disk**
6. Choose the Python plugin file you want to install (either `parametric_curve_node.py` or `parametric_surface_node.py`)
7. Enable the plugin by checking the checkbox next to its name

## Usage

### Parametric Curve

After installation, the Parametric Curve node will be available in the Geometry Nodes editor:

1. Click on the node
2. Press **N** to open the side panel
3. Look for the **"Parametric curve"** label on the right side
4. Modify the parametric equations to create your desired curve

### Parametric Surface

Similar to the Parametric Curve, the Parametric Surface node allows you to define custom surface equations through the node interface.

## Compatibility

These plugins are tested for **Blender v 5.0.1**.

For more information about Blender, visit [https://www.blender.org](https://www.blender.org)

## License

See the [LICENSE](LICENSE) file for details.

## Author
Alessio Fumagalli
