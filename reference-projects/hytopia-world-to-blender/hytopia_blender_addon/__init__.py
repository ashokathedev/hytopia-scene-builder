"""
Hytopia World to Blender Import Addon

A Blender addon for importing Hytopia world maps with proper texture and material support.
Designed to handle large worlds efficiently with robust error handling.
"""

bl_info = {
    "name": "Hytopia World Importer",
    "author": "Hytopia Team",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > Hytopia Tab",
    "description": "Import Hytopia world maps into Blender with blocks, textures, and entities",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}

import bpy

# Import modules with error handling
try:
    from . import ui_panel
    from . import hytopia_importer
    from . import mesh_generator
    from . import material_manager
    from . import utils
    
    # Flag to track if modules loaded successfully
    modules_loaded = True
    import_error = None
    
except ImportError as e:
    # Store error for reporting
    modules_loaded = False
    import_error = str(e)
    print(f"Hytopia Addon Import Error: {e}")


def register():
    """Register the addon with Blender."""
    if not modules_loaded:
        # Show error message if modules failed to load
        def draw_error(self, context):
            self.layout.label(text=f"Hytopia addon failed to load: {import_error}", icon='ERROR')
        
        bpy.types.VIEW3D_PT_view3d_properties.append(draw_error)
        print(f"Hytopia addon registration failed: {import_error}")
        return
    
    try:
        # Register UI components
        ui_panel.register()
        
        print("Hytopia World Importer addon registered successfully")
        
    except Exception as e:
        print(f"Error registering Hytopia addon: {e}")
        raise


def unregister():
    """Unregister the addon from Blender."""
    if not modules_loaded:
        return
    
    try:
        # Unregister UI components  
        ui_panel.unregister()
        
        print("Hytopia World Importer addon unregistered")
        
    except Exception as e:
        print(f"Error unregistering Hytopia addon: {e}")


if __name__ == "__main__":
    register() 