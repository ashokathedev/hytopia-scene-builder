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
            
            # Import blocks if requested
            if import_blocks:
                success = self._import_blocks(map_data, block_registry, min_bounds, max_bounds, cull_faces)
                if not success:
                    print("Block import failed")
                    return False
            
            # Import entities if requested  
            if import_entities:
                success = self._import_entities(map_data, model_base_path, min_bounds, max_bounds)
                if not success:
                    print("Entity import failed (continuing anyway)")
                    # Don't return False for entity failures - blocks are more important
            
            print("=== Import Complete ===")
            self._print_import_stats()
            
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
                      cull_faces: bool) -> bool:
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
            self._create_blocks_by_type(filtered_blocks, block_registry, cull_faces)
            
            print(f"Successfully imported {len(filtered_blocks)} blocks")
            return True
            
        except Exception as e:
            print(f"Error importing blocks: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_blocks_by_type(self, filtered_blocks: Dict[Tuple[float, float, float], int],
                              block_registry: Dict[int, Dict[str, Any]],
                              cull_faces: bool) -> bool:
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
                    cull_faces=False  # Don't cull between different objects
                )
                
                if not mesh:
                    continue
                
                # Create mesh object
                mesh_name = f"Hytopia_{block_name}"
                mesh_obj = bpy.data.objects.new(mesh_name, mesh)
                bpy.context.collection.objects.link(mesh_obj)
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
                
                # Debug: Create a simple test cube to verify material works
                if len(coord_list) <= 4 and material.name == "hytopia_grass":  # Only for small grass test
                    print(f"🧪 Creating test cube for material: {material.name}")
                    bpy.ops.mesh.primitive_cube_add(location=(10, 10, 0))
                    test_cube = bpy.context.active_object
                    test_cube.name = f"TEST_{material.name}"
                    test_cube.data.materials.append(material)
                    self.imported_objects.append(test_cube)
                
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
                        max_bounds: Tuple[float, float, float]) -> bool:
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
                    if self._import_single_entity_clean(entity_data, coords, model_base_path):
                        imported_count += 1
                except Exception as e:
                    print(f"Warning: Failed to import entity at {coords}: {e}")
                    continue  # Continue with other entities
            
            print(f"Successfully imported {imported_count}/{len(filtered_entities)} entities")
            return imported_count > 0 or len(filtered_entities) == 0
            
        except Exception as e:
            print(f"Error importing entities: {e}")
            return False
    
    def _import_single_entity_clean(self, entity_data: Dict[str, Any], 
                                    coords: Tuple[float, float, float],
                                    model_base_path: str) -> bool:
        """
        Clean implementation of single entity import using world editor algorithm.
        
        Returns:
            True if successful
        """
        model_uri = entity_data.get('modelUri', '')
        if not model_uri:
            print(f"Warning: Entity has no modelUri")
            return False
        
        model_path = os.path.join(model_base_path, model_uri)
        
        # Check if model file exists
        if not os.path.exists(model_path):
            print(f"Warning: Model file not found: {model_path}")
            return False
        
        # Only support GLTF/GLB files
        if not model_path.lower().endswith(('.gltf', '.glb')):
            print(f"Warning: Unsupported model format: {model_path}")
            return False
        
        entity_name = entity_data.get('name', 'entity')
        scale = entity_data.get('modelScale', 1.0)
        
        try:
            print(f"   Importing model: {model_uri}")
            
            # Step 1: Import GLTF at origin
            model_object = self._import_gltf_at_origin(model_path, entity_name)
            if not model_object:
                return False
            
            # Step 2: Apply scale first
            model_object.scale = (scale, scale, scale)
            
            # Step 3: Force update to apply scaling
            bpy.context.view_layer.update()
            
            # Step 4: Center bottom of scaled model at 0,0,0 
            self._center_model_bottom_at_origin(model_object)
            
            # Step 5: Move to translated Hytopia coordinates 
            # Coordinate transformation: Hytopia (X,Y,Z) -> Blender (-X, Z, Y)
            # Only apply centering offset to height coordinate (Blender Z), preserve exact X,Y values
            current_location = model_object.location
            
            final_position = (
                -coords[0],                              # Hytopia X -> Blender X (flipped, no offset)
                coords[2],                               # Hytopia Z -> Blender Y (no offset)
                current_location[2] + coords[1]          # Hytopia Y -> Blender Z (with height centering offset)
            )
            model_object.location = final_position
            
            # Step 6: Apply rotation if specified
            self._apply_rotation(model_object, entity_data)
            
            # Step 7: Force final update and track object
            bpy.context.view_layer.update()
            self.imported_objects.append(model_object)
            
            print(f"✓ Imported: {model_object.name}")
            print(f"   Hytopia coords: {coords}")
            print(f"   Final position: {final_position}")
            print(f"   Scale: {scale}")
            print(f"   Height centering offset applied to Z: {current_location[2]:.3f}")
            
            return True
                
        except Exception as e:
            print(f"Error importing model {model_path}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _import_gltf_at_origin(self, model_path: str, entity_name: str) -> Optional[bpy.types.Object]:
        """
        Import GLTF at origin, clean up objects, and return single mesh object.
        
        Returns:
            Single mesh object or None if failed
        """
        # Clear current selection
        bpy.ops.object.select_all(action='DESELECT')
        
        # Import the GLTF
        bpy.ops.import_scene.gltf(filepath=model_path)
        
        # Get imported objects
        imported_objects = [obj for obj in bpy.context.selected_objects]
        
        if not imported_objects:
            print(f"Warning: No objects imported from {model_path}")
            return None
        
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
            return None
        
        # Join multiple mesh objects into one if needed
        final_object = None
        if len(mesh_objects) > 1:
            print(f"   Joining {len(mesh_objects)} mesh objects")
            # Select all mesh objects
            bpy.ops.object.select_all(action='DESELECT')
            for obj in mesh_objects:
                obj.select_set(True)
            
            # Set first as active and join
            bpy.context.view_layer.objects.active = mesh_objects[0]
            bpy.ops.object.join()
            final_object = bpy.context.active_object
        else:
            final_object = mesh_objects[0]
        
        # Clean up object
        if final_object.animation_data:
            final_object.animation_data_clear()
            
        for modifier in final_object.modifiers[:]:
            if modifier.type == 'ARMATURE':
                final_object.modifiers.remove(modifier)
        
        # Set name and reset all transforms to origin
        final_object.name = f"entity_{entity_name}"
        final_object.location = (0, 0, 0)
        final_object.rotation_euler = (0, 0, 0) 
        final_object.scale = (1, 1, 1)
        
        return final_object
    
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
    
    def _apply_rotation(self, obj: bpy.types.Object, entity_data: Dict[str, Any]):
        """
        Apply rotation to object if specified in entity data.
        """
        rotation_data = entity_data.get('rigidBodyOptions', {}).get('rotation')
        if not rotation_data:
            return
            
        from mathutils import Quaternion
        
        # Hytopia quaternion: {x, y, z, w}
        # Convert coordinate system: Hytopia Y-up to Blender Z-up
        quat = Quaternion((
            rotation_data.get('w', 1.0),    # w (scalar)
            rotation_data.get('x', 0.0),    # x stays x
            rotation_data.get('z', 0.0),    # Hytopia z -> Blender y  
            rotation_data.get('y', 0.0)     # Hytopia y -> Blender z
        ))
        
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = quat
        
        print(f"   Applied rotation: {quat}")
    
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
        
        print("Cleared imported objects")
    
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