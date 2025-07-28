"""
Core Hytopia world import logic
"""
import bpy
import os
from typing import Tuple, Optional, Dict, Any
from .utils import (
    load_hytopia_map, 
    validate_bounds, 
    filter_blocks_in_bounds,
    filter_entities_in_bounds,
    get_block_registry,
    report_progress
)
from .mesh_generator import HytopiaBlockMesh, assign_materials_to_mesh
from .material_manager import HytopiaMaterialManager


class HytopiaWorldImporter:
    """
    Main importer class for Hytopia worlds.
    
    Coordinates the import process, handles errors gracefully,
    and provides progress feedback.
    """
    
    def __init__(self):
        self.material_manager = HytopiaMaterialManager()
        self.mesh_generator = HytopiaBlockMesh()
        self.imported_objects = []  # Track imported objects for cleanup
        self.world_map_collection = None  # Collection for all imported map content
        
    def import_world(self,
                    map_file_path: str,
                    texture_base_path: str,
                    model_base_path: str,
                    min_bounds: Tuple[float, float, float],
                    max_bounds: Tuple[float, float, float],
                    import_blocks: bool = True,
                    import_entities: bool = True,
                    cull_faces: bool = True) -> bool:
        """
        Import Hytopia world with specified parameters.
        
        Args:
            map_file_path: Path to Hytopia JSON map file
            texture_base_path: Base directory for block textures
            model_base_path: Base directory for entity models
            min_bounds: (x, y, z) minimum bounds for import
            max_bounds: (x, y, z) maximum bounds for import
            import_blocks: Whether to import terrain blocks
            import_entities: Whether to import entities/models
            cull_faces: Whether to cull hidden faces between blocks
            
        Returns:
            True if import successful, False otherwise
        """
        print("=== Starting Hytopia World Import ===")
        
        try:
            # Validate inputs
            if not self._validate_inputs(map_file_path, texture_base_path, model_base_path, 
                                       min_bounds, max_bounds):
                return False
            
            # Load map data
            print("Loading map file...")
            map_data = load_hytopia_map(map_file_path)
            if not map_data:
                print("Failed to load map file")
                return False
            
            # Setup material manager
            if texture_base_path:
                print(f"Using texture directory: {texture_base_path}")
                self.material_manager.set_texture_base_path(texture_base_path)
            else:
                print("No texture directory specified - using fallback colors only")
                self.material_manager.set_texture_base_path("")
            
            # Get block registry
            block_registry = get_block_registry(map_data)
            print(f"Loaded {len(block_registry)} block types")
            
            # Calculate centering offset to move imported content to origin
            # Hytopia coordinates: (X, Y, Z) where Y is height
            # Blender coordinates: (X, Z, Y) where Z is height
            # We want to center the imported area at (0,0,0) in Blender
            center_offset = (
                -(min_bounds[0] + max_bounds[0]) / 2,  # Center X: negate for Blender X
                -(min_bounds[2] + max_bounds[2]) / 2,  # Center Z: negate for Blender Y (Hytopia Z)
                0  # Keep Y (height) as is
            )
            print(f"Centering offset: {center_offset} (will move imported content to origin)")
            
            # Create or get the world map collection
            self._setup_world_map_collection()
            
            # Import blocks if requested
            if import_blocks:
                success = self._import_blocks(map_data, block_registry, min_bounds, max_bounds, cull_faces, center_offset)
                if not success:
                    print("Block import failed")
                    return False
            
            # Import entities if requested  
            if import_entities:
                success = self._import_entities(map_data, model_base_path, min_bounds, max_bounds, center_offset)
                if not success:
                    print("Entity import failed (continuing anyway)")
                    # Don't return False for entity failures - blocks are more important
            
            print("=== Import Complete ===")
            self._print_import_stats()
            
            # Hide relationship lines in viewport overlay for all imported objects
            self._hide_relationship_lines()
            
            # Final cleanup: ensure ALL imported objects are in the collection
            self._ensure_all_objects_in_collection()
            
            return True
            
        except Exception as e:
            print(f"Error during import: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _validate_inputs(self, map_file_path: str, texture_base_path: str, model_base_path: str,
                        min_bounds: Tuple[float, float, float], 
                        max_bounds: Tuple[float, float, float]) -> bool:
        """
        Validate all input parameters before import.
        
        Returns:
            True if all inputs are valid
        """
        # Check map file
        if not os.path.exists(map_file_path):
            print(f"Error: Map file not found: {map_file_path}")
            return False
        
        # Check bounds
        if not validate_bounds(min_bounds, max_bounds):
            return False
        
        # Check texture directory (warn but don't fail)
        if texture_base_path and not os.path.exists(texture_base_path):
            print(f"Warning: Texture directory not found: {texture_base_path}")
            print("Proceeding with colored fallback materials")
        
        # Check model directory (warn but don't fail)
        if model_base_path and not os.path.exists(model_base_path):
            print(f"Warning: Model directory not found: {model_base_path}")
            print("Entity import will be skipped")
        
        return True
    
    def _import_blocks(self, map_data: Dict[str, Any], 
                      block_registry: Dict[int, Dict[str, Any]],
                      min_bounds: Tuple[float, float, float],
                      max_bounds: Tuple[float, float, float],
                      cull_faces: bool,
                      center_offset: Tuple[float, float, float]) -> bool:
        """
        Import terrain blocks as mesh.
        
        Returns:
            True if successful
        """
        try:
            print("Filtering blocks in bounds...")
            filtered_blocks = filter_blocks_in_bounds(map_data, min_bounds, max_bounds)
            
            if not filtered_blocks:
                print("No blocks found in specified bounds")
                return True  # Not an error, just empty region
            
            print(f"Generating mesh for {len(filtered_blocks)} blocks...")
            
            # Use the block-by-type approach (no fallback needed)
            self._create_blocks_by_type(filtered_blocks, block_registry, cull_faces, center_offset)
            
            print(f"Successfully imported {len(filtered_blocks)} blocks")
            return True
            
        except Exception as e:
            print(f"Error importing blocks: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_blocks_by_type(self, filtered_blocks: Dict[Tuple[float, float, float], int],
                              block_registry: Dict[int, Dict[str, Any]],
                              cull_faces: bool,
                              center_offset: Tuple[float, float, float]) -> bool:
        """
        Create separate mesh objects for each block type with proper materials.
        
        Returns:
            True if successful
        """
        try:
            # Group blocks by type
            blocks_by_type = {}
            for coords, block_id in filtered_blocks.items():
                if block_id not in blocks_by_type:
                    blocks_by_type[block_id] = []
                blocks_by_type[block_id].append(coords)
            
            print(f"Creating {len(blocks_by_type)} separate meshes by block type...")
            
            # Create mesh for each block type
            for block_id, coord_list in blocks_by_type.items():
                if block_id not in block_registry:
                    continue
                    
                block_type = block_registry[block_id]
                block_name = block_type.get('name', f'block_{block_id}')
                
                # Create blocks dict for this type
                type_blocks = {coords: block_id for coords in coord_list}
                
                # Generate mesh for this block type
                mesh = self.mesh_generator.create_block_mesh(
                    type_blocks, 
                    block_registry, 
                    cull_faces=False,  # Don't cull between different objects
                    center_offset=center_offset
                )
                
                if not mesh:
                    continue
                
                # Create mesh object
                mesh_name = f"Hytopia_{block_name}"
                mesh_obj = bpy.data.objects.new(mesh_name, mesh)
                
                # Move to world map collection
                self._move_object_to_world_map_collection(mesh_obj)
                
                self.imported_objects.append(mesh_obj)
                
                # Debug: Check if mesh has UV coordinates
                has_uv = len(mesh.uv_layers) > 0
                print(f"   UV layers: {len(mesh.uv_layers)} ({'✓' if has_uv else '❌ NO UV'})")
                
                # Create and assign single material for this block type
                material = self.material_manager.get_or_create_material(block_type)
                mesh_obj.data.materials.append(material)
                
                # Assign material to all faces
                for face in mesh.polygons:
                    face.material_index = 0
                
                print(f"Created mesh for {len(coord_list)} {block_name} blocks")
            
            # Set viewport to Material Preview mode
            self._set_viewport_material_preview()
            
            return True
            
        except Exception as e:
            print(f"Error creating blocks by type: {e}")
            return False
    
    def _set_viewport_material_preview(self):
        """Set the 3D viewport to Material Preview mode to show materials."""
        try:
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.shading.type = 'MATERIAL'
                            print("Set viewport to Material Preview mode")
                            break
        except Exception as e:
            print(f"Could not set viewport mode: {e}")
    
    def _import_entities(self, map_data: Dict[str, Any],
                        model_base_path: str,
                        min_bounds: Tuple[float, float, float],
                        max_bounds: Tuple[float, float, float],
                        center_offset: Tuple[float, float, float]) -> bool:
        """
        Import entities/models with clean, accurate positioning.
        
        Returns:
            True if successful
        """
        try:
            print("Filtering entities in bounds...")
            filtered_entities = filter_entities_in_bounds(map_data, min_bounds, max_bounds)
            
            if not filtered_entities:
                print("No entities found in specified bounds")
                return True
            
            print(f"Importing {len(filtered_entities)} entities...")
            
            imported_count = 0
            for coords, entity_data in filtered_entities.items():
                try:
                    if self._import_single_entity(entity_data, coords, model_base_path, center_offset):
                        imported_count += 1
                except Exception as e:
                    print(f"Warning: Failed to import entity at {coords}: {e}")
                    continue  # Continue with other entities
            
            print(f"Successfully imported {imported_count}/{len(filtered_entities)} entities")
            return imported_count > 0 or len(filtered_entities) == 0
            
        except Exception as e:
            print(f"Error importing entities: {e}")
            return False
    
    def _import_single_entity(self, entity_data: Dict[str, Any], 
                             coords: Tuple[float, float, float],
                             model_base_path: str,
                             center_offset: Tuple[float, float, float]) -> bool:
        """
        Import a single entity with clean order of operations.
        
        Steps:
        1. Import GLTF
        2. Scale
        3. Rotate  
        4. Center bottom at origin
        5. Final positioning
        """
        model_uri = entity_data.get('modelUri', '')
        if not model_uri:
            print(f"Warning: No model URI specified for entity")
            return False
            
        model_path = os.path.join(model_base_path, model_uri)
        if not os.path.exists(model_path):
            print(f"Error: Model file not found: {model_path}")
            return False
            
        entity_name = entity_data.get('name', 'entity')
        scale = entity_data.get('modelScale', 1.0)
        
        try:
            print(f"   Importing model: {model_uri}")
            
            # Step 1: Import GLTF
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.import_scene.gltf(filepath=model_path)
            
            # Get the imported object
            imported_objects = [obj for obj in bpy.context.selected_objects]
            if not imported_objects:
                print(f"Warning: No objects imported from {model_path}")
                return False
            
            # Rename imported objects with actual GLTF filename
            self._rename_imported_objects(imported_objects, model_uri)
            
            # Set specular to 0 for all GLTF materials
            self._set_gltf_materials_specular_to_zero(imported_objects)
            
            # Filter to mesh objects and clean up non-mesh objects
            mesh_objects = []
            for obj in imported_objects:
                if obj.type == 'MESH' and obj.name in bpy.data.objects:
                    mesh_objects.append(obj)
                elif obj.type in ['ARMATURE', 'LIGHT', 'CAMERA']:
                    # Remove non-mesh objects
                    try:
                        bpy.data.objects.remove(obj, do_unlink=True)
                    except:
                        pass
            
            if not mesh_objects:
                print(f"Warning: No mesh objects found in {model_path}")
                return False
            
            # Join multiple mesh objects into one if needed
            model_object = None
            if len(mesh_objects) > 1:
                print(f"   Joining {len(mesh_objects)} mesh objects")
                # Select all mesh objects
                bpy.ops.object.select_all(action='DESELECT')
                for obj in mesh_objects:
                    obj.select_set(True)
                
                # Set first as active and join
                bpy.context.view_layer.objects.active = mesh_objects[0]
                bpy.ops.object.join()
                model_object = bpy.context.active_object
            else:
                model_object = mesh_objects[0]
            
            # Clean up object
            if model_object.animation_data:
                model_object.animation_data_clear()
                
            for modifier in model_object.modifiers[:]:
                if modifier.type == 'ARMATURE':
                    model_object.modifiers.remove(modifier)
            
            # Set name using the clean filename from GLTF
            filename = os.path.splitext(os.path.basename(model_uri))[0]
            clean_filename = filename.replace('-', '_').replace(' ', '_')
            model_object.name = f"entity_{clean_filename}"
            model_object.location = (0, 0, 0)
            model_object.rotation_euler = (0, 0, 0)  # Reset GLTF's built-in rotation to (0,0,0)
            model_object.scale = (1, 1, 1)
            
            # Apply the default rotation to the geometry (bake it in)
            bpy.context.view_layer.objects.active = model_object
            model_object.select_set(True)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
            model_object.select_set(False)
            
            print(f"   Step 1: GLTF imported and cleaned up")
            print(f"   Step 1.5: Applied default rotation to geometry (baked in)")
            
            # Step 2: Scale
            model_object.scale = (scale, scale, scale)
            bpy.context.view_layer.update()  # Force update to apply scaling
            print(f"   Step 2: Applied scale: {scale}")
            
            # Step 3: Set origin to geometry center (for proper rotation pivot)
            bpy.context.view_layer.objects.active = model_object
            model_object.select_set(True)
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
            model_object.select_set(False)
            print(f"   Step 3: Set origin to geometry center")
            
            # Step 4: Rotate (apply rotation before centering)
            self._apply_entity_rotation(model_object, entity_data)
            
            # Add -180 degrees to Z rotation
            import math
            current_rotation = model_object.rotation_euler
            model_object.rotation_euler = (
                current_rotation[0],
                current_rotation[1], 
                current_rotation[2] - math.radians(180)
            )
            print(f"   Step 4: Applied rotation + -180° Z offset")
            
            # Step 5: Center bottom at origin
            self._center_model_bottom_at_origin(model_object)
            print(f"   Step 5: Centered bottom at origin")
            
            # Step 6: Final positioning
            # Get current location after centering
            current_location = model_object.location
            
            # Calculate bounding box center offset for X and Y only
            # from mathutils import Vector
            # world_matrix = model_object.matrix_world
            # local_bbox = [Vector(corner) for corner in model_object.bound_box]
            # world_bbox_corners = [world_matrix @ corner for corner in local_bbox]
            
            # Calculate center on X and Y only
            # min_x = min(corner.x for corner in world_bbox_corners)
            # max_x = max(corner.x for corner in world_bbox_corners)
            # min_y = min(corner.y for corner in world_bbox_corners)
            # max_y = max(corner.y for corner in world_bbox_corners)
            
            # center_x = (min_x + max_x) / 2
            # center_y = (min_y + max_y) / 2
            
            # X,Y bounding box offset (negative to compensate)
            # bbox_offset_x = center_x
            # bbox_offset_y = center_y
            
            # Coordinate transformation: Hytopia (X,Y,Z) -> Blender (-X, Z, Y)
            # Apply bounding box offset to X,Y only, then add position offsets
            # Apply center offset to move imported content to origin
            final_position = (
                -coords[0] + 1 + center_offset[0],          # Hytopia X -> Blender X (flipped) + center offset
                coords[2] - 1 + center_offset[1],           # Hytopia Z -> Blender Y + center offset
                current_location[2] + coords[1] + center_offset[2]  # Hytopia Y -> Blender Z + center offset
            )
            model_object.location = final_position
            print(f"   Step 6: Positioned at: {final_position}")
            print(f"   Height centering offset applied to Z: {current_location[2]:.3f}")
            
            # Move to world map collection and track object
            self._move_object_to_world_map_collection(model_object)
            bpy.context.view_layer.update()
            self.imported_objects.append(model_object)
            
            print(f"✓ Imported: {model_object.name}")
            return True
                
        except Exception as e:
            print(f"Error importing model {model_path}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _center_model_bottom_at_origin(self, obj: bpy.types.Object):
        """
        Center the bottom of the scaled model at Blender's origin (0,0,0).
        
        This calculates the scaled bounding box and moves the model so that:
        - The bottom (lowest point) is at Y=0
        - The center of X and Z axes are at 0
        """
        if obj.type != 'MESH' or not obj.data.vertices:
            return
            
        from mathutils import Vector
        
        # Get the object's world matrix to account for scale
        world_matrix = obj.matrix_world
        
        # Transform all bounding box corners to world space
        local_bbox = [Vector(corner) for corner in obj.bound_box]
        world_bbox_corners = [world_matrix @ corner for corner in local_bbox]
        
        # Find the min/max in world space
        min_x = min(corner.x for corner in world_bbox_corners)
        max_x = max(corner.x for corner in world_bbox_corners)
        min_y = min(corner.y for corner in world_bbox_corners)
        max_y = max(corner.y for corner in world_bbox_corners)
        min_z = min(corner.z for corner in world_bbox_corners)
        max_z = max(corner.z for corner in world_bbox_corners)
        
        # Calculate center on X and Z, bottom on Y
        center_x = (min_x + max_x) / 2
        center_z = (min_z + max_z) / 2
        
        # Calculate offset needed to center bottom at origin
        offset = (
            -center_x,  # Center X at 0
            -min_y,     # Bottom Y at 0  
            -center_z   # Center Z at 0
        )
        
        # Apply the offset
        current_location = obj.location
        obj.location = (
            current_location[0] + offset[0],
            current_location[1] + offset[1],
            current_location[2] + offset[2]
        )
        
        print(f"   Scaled bbox: ({min_x:.3f},{min_y:.3f},{min_z:.3f}) to ({max_x:.3f},{max_y:.3f},{max_z:.3f})")
        print(f"   Center X,Z: ({center_x:.3f}, {center_z:.3f}), Bottom Y: {min_y:.3f}")
        print(f"   Applied offset: {offset}")
        print(f"   Model bottom now centered at origin")
    
    def _apply_entity_rotation(self, obj: bpy.types.Object, entity_data: Dict[str, Any]):
        """
        Apply rotation to object if specified in entity data.
        """
        rotation_data = entity_data.get('rigidBodyOptions', {}).get('rotation')
        if not rotation_data:
            return
            
        from mathutils import Quaternion
        
        # Debug: Print the raw rotation data from JSON
        print(f"   Raw rotation data: {rotation_data}")
        
        # Convert Hytopia quaternion to Blender quaternion
        # Hytopia: Y-up, Blender: Z-up
        # Convert: Hytopia (x,y,z,w) -> Blender (x,z,y,w)
        hytopia_quat = Quaternion((
            rotation_data.get('w', 1.0),    # w (scalar)
            rotation_data.get('x', 0.0),    # x 
            rotation_data.get('z', 0.0),    # Hytopia z -> Blender y  
            rotation_data.get('y', 0.0)     # Hytopia y -> Blender z
        ))
        
        # Convert quaternion to euler angles
        euler = hytopia_quat.to_euler()
        
        print(f"   Hytopia quaternion (w,x,y,z): ({hytopia_quat.w:.3f}, {hytopia_quat.x:.3f}, {hytopia_quat.y:.3f}, {hytopia_quat.z:.3f})")
        print(f"   Converted to euler (X,Y,Z): ({euler.x:.3f}, {euler.y:.3f}, {euler.z:.3f})")
        
        # Apply as euler rotation
        obj.rotation_mode = 'XYZ'
        obj.rotation_euler = euler
    
    def clear_imported_objects(self):
        """
        Clear previously imported objects from scene.
        """
        print("Clearing previously imported objects...")
        
        for obj in self.imported_objects:
            try:
                if obj and obj.name in bpy.data.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
            except:
                pass  # Object may have been deleted already
        
        self.imported_objects.clear()
        
        # Clear materials cache
        self.material_manager.clear_cache()
        
        # Clear world map collection if it exists and is empty
        if self.world_map_collection and len(self.world_map_collection.objects) == 0:
            try:
                bpy.data.collections.remove(self.world_map_collection)
                self.world_map_collection = None
                print("Removed empty World Map collection")
            except:
                pass
        
        print("Cleared imported objects")
    
    def _hide_relationship_lines(self):
        """
        Hide relationship lines in viewport overlay for all imported objects.
        This makes the viewport cleaner by hiding parent-child relationship lines.
        """
        try:
            for obj in self.imported_objects:
                if hasattr(obj, 'show_in_front'):
                    obj.show_in_front = False
                if hasattr(obj, 'show_axis'):
                    obj.show_axis = False
                if hasattr(obj, 'show_name'):
                    obj.show_name = False
                if hasattr(obj, 'show_bounds'):
                    obj.show_bounds = False
                    
            # Also hide relationship lines in viewport overlay settings
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Hide relationship lines
                            if hasattr(space, 'overlay'):
                                if hasattr(space.overlay, 'show_relationship_lines'):
                                    space.overlay.show_relationship_lines = False
                                if hasattr(space.overlay, 'show_extra_indices'):
                                    space.overlay.show_extra_indices = False
                                if hasattr(space.overlay, 'show_face_center'):
                                    space.overlay.show_face_center = False
                                    
            print("✓ Hidden relationship lines in viewport overlay")
            
        except Exception as e:
            print(f"Warning: Could not hide relationship lines: {e}")
    
    def _rename_imported_objects(self, imported_objects: list, model_uri: str):
        """
        Rename imported GLTF objects with the actual filename instead of generic names.
        
        Args:
            imported_objects: List of imported Blender objects
            model_uri: The original GLTF file path/name
        """
        try:
            # Extract filename without extension and path
            filename = os.path.splitext(os.path.basename(model_uri))[0]
            
            # Clean filename for Blender object naming
            clean_filename = filename.replace('-', '_').replace(' ', '_')
            
            # Rename all imported objects
            for i, obj in enumerate(imported_objects):
                if obj and obj.name in bpy.data.objects:
                    if i == 0:
                        # First object gets the clean filename
                        obj.name = clean_filename
                    else:
                        # Additional objects get numbered suffix
                        obj.name = f"{clean_filename}_{i+1:03d}"
                    
                    print(f"   Renamed: {obj.name}")
                    
        except Exception as e:
            print(f"Warning: Could not rename imported objects: {e}")
    
    def _set_gltf_materials_specular_to_zero(self, imported_objects: list):
        """
        Set specular IOR to 0 for all materials in imported GLTF objects.
        
        Args:
            imported_objects: List of imported Blender objects
        """
        try:
            for obj in imported_objects:
                if obj and hasattr(obj, 'data') and hasattr(obj.data, 'materials'):
                    for material in obj.data.materials:
                        if material and material.use_nodes:
                            for node in material.node_tree.nodes:
                                if node.type == 'BSDF_PRINCIPLED':
                                    # Set Specular IOR Level to 0
                                    if 'Specular IOR Level' in node.inputs:
                                        node.inputs['Specular IOR Level'].default_value = 0.0
                                    # Also set Specular to 0 for older Blender versions
                                    if 'Specular' in node.inputs:
                                        node.inputs['Specular'].default_value = 0.0
                                    print(f"   Set specular to 0 for material: {material.name}")
                                    break
                                    
        except Exception as e:
            print(f"Warning: Could not set GLTF materials specular to 0: {e}")
    
    def _setup_world_map_collection(self):
        """
        Create or get the world map collection for organizing imported content.
        """
        try:
            collection_name = "World Map"
            
            # Check if collection already exists
            if collection_name in bpy.data.collections:
                self.world_map_collection = bpy.data.collections[collection_name]
                print(f"Using existing collection: {collection_name}")
            else:
                # Create new collection
                self.world_map_collection = bpy.data.collections.new(collection_name)
                # Link to scene
                bpy.context.scene.collection.children.link(self.world_map_collection)
                print(f"Created new collection: {collection_name}")
                
        except Exception as e:
            print(f"Warning: Could not setup world map collection: {e}")
            self.world_map_collection = None
    
    def _move_object_to_world_map_collection(self, obj):
        """
        Move an object to the world map collection while preserving visual hierarchy.
        Only moves the top-level parent - children follow automatically.
        
        Args:
            obj: Blender object to move
        """
        try:
            if self.world_map_collection and obj:
                # Find the top-level parent of this object
                top_parent = self._find_top_level_parent(obj)
                
                # Only move the top-level parent to the collection
                # Children will automatically be included through the hierarchy
                if top_parent and top_parent.name in bpy.data.objects:
                    # IMPORTANT: Remove from ALL collections first
                    collections_to_remove = list(top_parent.users_collection)
                    for collection in collections_to_remove:
                        collection.objects.unlink(top_parent)
                    
                    # Add ONLY to world map collection
                    self.world_map_collection.objects.link(top_parent)
                    
                    print(f"   Moved top-level parent '{top_parent.name}' to World Map collection")
                
        except Exception as e:
            print(f"Warning: Could not move object to world map collection: {e}")
    
    def _find_top_level_parent(self, obj):
        """
        Find the top-level parent of an object (the root of its hierarchy).
        
        Args:
            obj: Blender object
            
        Returns:
            Top-level parent object
        """
        current = obj
        while current.parent:
            current = current.parent
        return current
    
    def _get_all_children(self, obj):
        """
        Recursively get all children of an object.
        
        Args:
            obj: Parent object
            
        Returns:
            List of all child objects
        """
        children = []
        for child in obj.children:
            children.append(child)
            children.extend(self._get_all_children(child))
        return children
    
    def _ensure_all_objects_in_collection(self):
        """
        Final cleanup: ensure ALL imported objects and their hierarchies are in the World Map collection.
        This catches any objects that might have been missed during the import process.
        """
        try:
            if not self.world_map_collection:
                return
                
            print("Ensuring all imported objects are in World Map collection...")
            
            # Get all top-level parents that should be in the collection
            top_level_parents = set()
            
            # Add all imported objects - find their top-level parents
            for obj in self.imported_objects:
                if obj and obj.name in bpy.data.objects:
                    top_parent = self._find_top_level_parent(obj)
                    top_level_parents.add(top_parent)
            
            # Also check for any objects with "hytopia" or "entity_" in their name
            # that might not be in our imported_objects list
            for obj in bpy.data.objects:
                if (obj.name.lower().startswith('hytopia_') or 
                    obj.name.lower().startswith('entity_') or
                    obj.name.lower().startswith('bone_cluster') or
                    obj.name.lower().startswith('test_')):
                    top_parent = self._find_top_level_parent(obj)
                    top_level_parents.add(top_parent)
            
            # Move only the top-level parents to the collection
            moved_count = 0
            for top_parent in top_level_parents:
                if top_parent and top_parent.name in bpy.data.objects:
                    # Check if object is already ONLY in the world map collection
                    if (len(top_parent.users_collection) != 1 or 
                        self.world_map_collection not in top_parent.users_collection):
                        
                        # Remove from ALL collections first
                        collections_to_remove = list(top_parent.users_collection)
                        for collection in collections_to_remove:
                            collection.objects.unlink(top_parent)
                        
                        # Add ONLY to world map collection
                        self.world_map_collection.objects.link(top_parent)
                        moved_count += 1
                        print(f"   Moved top-level parent '{top_parent.name}' to World Map collection")
            
            if moved_count > 0:
                print(f"✓ Moved {moved_count} additional objects to World Map collection")
            else:
                print("✓ All objects already in World Map collection")
                
        except Exception as e:
            print(f"Warning: Could not ensure all objects in collection: {e}")
    
    def _print_import_stats(self):
        """Print statistics about the import process."""
        stats = self.material_manager.get_cache_stats()
        missing_count = stats['missing_textures']
        
        print("\n=== Import Statistics ===")
        print(f"Objects imported: {len(self.imported_objects)}")
        print(f"Materials created: {stats['cached_materials']}")
        print(f"Missing textures: {missing_count}")
        if missing_count > 0:
            print("Missing texture files:")
            for missing in sorted(self.material_manager.missing_textures):
                print(f"  - {missing}")
        print("========================\n")


# Convenience function for simple imports
def import_hytopia_world(map_file_path: str,
                        texture_base_path: str = "",
                        model_base_path: str = "",
                        min_bounds: Tuple[float, float, float] = (-10, 0, -10),
                        max_bounds: Tuple[float, float, float] = (10, 10, 10),
                        import_blocks: bool = True,
                        import_entities: bool = True,
                        cull_faces: bool = True) -> bool:
    """
    Convenience function to import a Hytopia world with default settings.
    
    Args:
        map_file_path: Path to Hytopia JSON map file
        texture_base_path: Base directory for block textures (optional)
        model_base_path: Base directory for entity models (optional)
        min_bounds: (x, y, z) minimum bounds for import
        max_bounds: (x, y, z) maximum bounds for import
        import_blocks: Whether to import terrain blocks
        import_entities: Whether to import entities/models
        cull_faces: Whether to cull hidden faces between blocks
        
    Returns:
        True if import successful
    """
    importer = HytopiaWorldImporter()
    return importer.import_world(
        map_file_path=map_file_path,
        texture_base_path=texture_base_path,
        model_base_path=model_base_path,
        min_bounds=min_bounds,
        max_bounds=max_bounds,
        import_blocks=import_blocks,
        import_entities=import_entities,
        cull_faces=cull_faces
    ) 