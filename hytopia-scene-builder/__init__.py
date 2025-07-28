"""
Hytopia Scene Builder Add-on

A comprehensive Blender add-on for building Hytopia scenes with three main components:
1. Map Importer - Import Hytopia world maps with blocks, textures, and entities
2. Character Importer - Import and manage Hytopia characters (Coming Soon)
3. Asset Importer - Import various Hytopia assets and models (Coming Soon)

Currently includes the Map Importer functionality with plans to expand.
"""

bl_info = {
    "name": "Hytopia Scene Builder",
    "author": "Hytopia Team",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > Hytopia Tab",
    "description": "Complete scene building toolkit for Hytopia - import maps, characters, and assets",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}

import bpy

# Import modules with error handling
try:
    # Map Importer Components (currently active)
    from . import ui_panel
    from .map_importer import hytopia_importer
    from .map_importer import mesh_generator
    from .map_importer import material_manager
    from .map_importer import utils
    
    # Character Importer Components (coming soon)
    # from . import character_importer
    
    # Asset Importer Components (coming soon)
    # from . import asset_importer
    
    # Flag to track if modules loaded successfully
    modules_loaded = True
    import_error = None
    
except ImportError as e:
    # Store error for reporting
    modules_loaded = False
    import_error = str(e)
    print(f"Hytopia Scene Builder Import Error: {e}")


def register():
    """Register the add-on with Blender."""
    if not modules_loaded:
        # Show error message if modules failed to load
        def draw_error(self, context):
            self.layout.label(text=f"Hytopia Scene Builder failed to load: {import_error}", icon='ERROR')
        
        bpy.types.VIEW3D_PT_view3d_properties.append(draw_error)
        print(f"Hytopia Scene Builder registration failed: {import_error}")
        return
    
    try:
        # Register Map Importer UI components
        ui_panel.register()
        
        # Future: Register Character Importer components
        # character_ui_panel.register()
        
        # Future: Register Asset Importer components  
        # asset_ui_panel.register()
        
        print("Hytopia Scene Builder add-on registered successfully")
        print("Available components: Map Importer")
        print("Coming soon: Character Importer, Asset Importer")
        
    except Exception as e:
        print(f"Error registering Hytopia Scene Builder: {e}")
        raise


def unregister():
    """Unregister the add-on from Blender."""
    if not modules_loaded:
        return
    
    try:
        # Unregister Map Importer UI components  
        ui_panel.unregister()
        
        # Future: Unregister other components
        # character_ui_panel.unregister()
        # asset_ui_panel.unregister()
        
        print("Hytopia Scene Builder add-on unregistered")
        
    except Exception as e:
        print(f"Error unregistering Hytopia Scene Builder: {e}")


if __name__ == "__main__":
    register() 