"""
Blender UI panel for Hytopia world import
"""
import os
import bpy
from bpy.props import StringProperty, BoolProperty, FloatVectorProperty
from bpy.types import Panel, Operator
from bpy_extras.io_utils import ImportHelper

from .hytopia_importer import HytopiaWorldImporter


class HYTOPIA_OT_import_world(Operator, ImportHelper):
    """Import Hytopia World"""
    bl_idname = "hytopia.import_world"
    bl_label = "Import Hytopia World"
    bl_description = "Import a Hytopia world map into Blender"
    
    # File browser filter
    filename_ext = ".json"
    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    # Import options
    texture_path: StringProperty(
        name="Texture Directory",
        description="Directory containing your custom block textures (required for textured blocks)",
        default="",
        subtype='DIR_PATH'
    )
    
    model_path: StringProperty(
        name="Model Directory", 
        description="Directory containing entity models",
        default="",
        subtype='DIR_PATH'
    )
    
    # Import bounds
    min_bounds: FloatVectorProperty(
        name="Min Bounds",
        description="Minimum X, Y, Z coordinates to import",
        default=(-50.0, 0.0, -50.0),
        size=3,
    )
    
    max_bounds: FloatVectorProperty(
        name="Max Bounds", 
        description="Maximum X, Y, Z coordinates to import",
        default=(50.0, 20.0, 50.0),
        size=3,
    )
    
    # Import options
    import_blocks: BoolProperty(
        name="Import Blocks",
        description="Import terrain blocks",
        default=True,
    )
    
    import_entities: BoolProperty(
        name="Import Entities",
        description="Import entities/models",
        default=True,
    )
    
    cull_faces: BoolProperty(
        name="Cull Hidden Faces",
        description="Remove faces between adjacent blocks to improve performance",
        default=True,
    )
    
    def execute(self, context):
        """Execute the import operation."""
        # Validate texture directory if provided
        if self.texture_path and not os.path.exists(self.texture_path):
            self.report({'WARNING'}, f"Texture directory not found: {self.texture_path}")
            self.report({'INFO'}, "Proceeding with colored fallback materials")
        elif self.texture_path:
            try:
                texture_files = [f for f in os.listdir(self.texture_path) 
                               if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                if not texture_files:
                    self.report({'WARNING'}, "No texture files found in specified directory")
                else:
                    self.report({'INFO'}, f"Found {len(texture_files)} texture files")
            except Exception as e:
                self.report({'WARNING'}, f"Could not read texture directory: {e}")
        
        try:
            # Create importer
            importer = HytopiaWorldImporter()
            
            # Perform import
            success = importer.import_world(
                map_file_path=self.filepath,
                texture_base_path=self.texture_path,
                model_base_path=self.model_path,
                min_bounds=tuple(self.min_bounds),
                max_bounds=tuple(self.max_bounds),
                import_blocks=self.import_blocks,
                import_entities=self.import_entities,
                cull_faces=self.cull_faces
            )
            
            if success:
                self.report({'INFO'}, "Hytopia world imported successfully")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to import Hytopia world")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Import error: {str(e)}")
            return {'CANCELLED'}
    
    def draw(self, context):
        """Draw the import options in the file browser."""
        layout = self.layout
        
        # Paths section
        box = layout.box()
        box.label(text="Asset Paths:")
        box.prop(self, "texture_path")
        box.prop(self, "model_path")
        
        # Bounds section
        box = layout.box()
        box.label(text="Import Bounds:")
        box.prop(self, "min_bounds")
        box.prop(self, "max_bounds")
        
        # Options section
        box = layout.box()
        box.label(text="Import Options:")
        box.prop(self, "import_blocks")
        box.prop(self, "import_entities")
        box.prop(self, "cull_faces")


class HYTOPIA_OT_clear_scene(Operator):
    """Clear Imported Objects"""
    bl_idname = "hytopia.clear_scene"
    bl_label = "Clear Imported Objects"
    bl_description = "Remove all previously imported Hytopia objects from the scene"
    
    def execute(self, context):
        """Execute the clear operation."""
        try:
            # Remove all objects with "hytopia" or "entity_" in name
            removed_count = 0
            objects_to_remove = []
            
            for obj in bpy.data.objects:
                if ("hytopia" in obj.name.lower() or 
                    obj.name.startswith("entity_") or
                    obj.name == "HytopiaWorld"):
                    objects_to_remove.append(obj)
            
            for obj in objects_to_remove:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed_count += 1
            
            # Clear orphaned materials
            for material in bpy.data.materials:
                if material.name.startswith("hytopia_") and material.users == 0:
                    bpy.data.materials.remove(material)
            
            self.report({'INFO'}, f"Removed {removed_count} Hytopia objects")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Clear error: {str(e)}")
            return {'CANCELLED'}


class HYTOPIA_PT_main_panel(Panel):
    """Main Hytopia Import Panel"""
    bl_label = "Hytopia World Import"
    bl_idname = "HYTOPIA_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Hytopia'
    
    def draw(self, context):
        layout = self.layout
        
        # Title
        layout.label(text="Hytopia World Importer", icon='WORLD')
        layout.separator()
        
        # Main import button
        layout.operator("hytopia.import_world", text="Import World", icon='IMPORT')
        
        layout.separator()
        
        # Quick settings
        box = layout.box()
        box.label(text="Quick Settings:")
        
        scene = context.scene
        hytopia_props = scene.hytopia_import_props
        
        box.prop(hytopia_props, "quick_texture_path")
        box.prop(hytopia_props, "quick_model_path")
        
        row = box.row()
        row.prop(hytopia_props, "quick_bounds_size")
        
        # Utilities
        layout.separator()
        layout.operator("hytopia.clear_scene", text="Clear Scene", icon='TRASH')
        
        # Info section  
        layout.separator()
        box = layout.box()
        box.label(text="Tips:")
        box.label(text="• Start with small bounds for testing", icon='INFO')
        box.label(text="• Face culling improves performance", icon='INFO')
        box.label(text="• Check console for detailed logs", icon='INFO')


class HytopiaImportProperties(bpy.types.PropertyGroup):
    """Properties for Hytopia import settings"""
    
    quick_texture_path: StringProperty(
        name="Texture Path",
        description="Quick setting for texture directory",
        default="",
        subtype='DIR_PATH'
    )
    
    quick_model_path: StringProperty(
        name="Model Path",
        description="Quick setting for model directory", 
        default="",
        subtype='DIR_PATH'
    )
    
    quick_bounds_size: bpy.props.FloatProperty(
        name="Bounds Size",
        description="Half-size of import bounds (creates -size to +size box)",
        default=25.0,
        min=1.0,
        max=500.0
    )


# Registration functions
classes = [
    HYTOPIA_OT_import_world,
    HYTOPIA_OT_clear_scene, 
    HYTOPIA_PT_main_panel,
    HytopiaImportProperties,
]


def register():
    """Register all UI classes and properties."""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register properties
    bpy.types.Scene.hytopia_import_props = bpy.props.PointerProperty(type=HytopiaImportProperties)


def unregister():
    """Unregister all UI classes and properties."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Unregister properties
    if hasattr(bpy.types.Scene, 'hytopia_import_props'):
        del bpy.types.Scene.hytopia_import_props 