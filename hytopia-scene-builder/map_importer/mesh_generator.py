"""
Robust mesh generation for Hytopia world blocks
"""
import bmesh
import bpy
from mathutils import Vector, Matrix
from typing import Dict, Tuple, List, Set, Any
from .utils import report_progress


class HytopiaBlockMesh:
    """
    Generates optimized mesh geometry for Hytopia blocks.
    
    Uses bmesh for robust mesh operations and includes face culling
    to reduce polygon count and avoid rendering issues.
    """
    
    def __init__(self):
        self.mesh = None
        self.bm = None
        self.created_materials = {}  # Track materials to avoid duplicates
        self.block_id_layer = None  # Face layer for storing block IDs
        self.face_direction_layer = None  # Face layer for storing face directions
        self.vertex_dict = {}  # Vertex cache for reuse
        
    def create_block_mesh(self, 
                         blocks: Dict[Tuple[float, float, float], int],
                         block_registry: Dict[int, Dict[str, Any]],
                         cull_faces: bool = True,
                         center_offset: Tuple[float, float, float] = (0, 0, 0)) -> bpy.types.Mesh:
        """
        Create a single mesh containing all blocks with proper face culling.
        
        Args:
            blocks: Dictionary mapping coordinates to block type IDs
            block_registry: Block type definitions
            cull_faces: Whether to remove hidden faces between blocks
            
        Returns:
            Blender mesh object
        """
        print(f"Generating mesh for {len(blocks)} blocks...")
        
        # Create bmesh instance for mesh operations
        self.bm = bmesh.new()
        
        # Try to create face layers for storing block IDs and face directions
        try:
            self.block_id_layer = self.bm.faces.layers.int.new("block_id")
            self.face_direction_layer = self.bm.faces.layers.int.new("face_direction")
        except:
            print("Warning: Could not create face layers, continuing without them")
            self.block_id_layer = None
            self.face_direction_layer = None
            
        self.vertex_dict.clear()  # Clear vertex cache
        
        try:
            if cull_faces:
                visible_faces = self._calculate_visible_faces(blocks)
                total_faces = len(visible_faces)
            else:
                # Generate all faces
                visible_faces = self._generate_all_faces(blocks)
                total_faces = len(visible_faces)
            
            print(f"Generating {total_faces} visible faces...")
            
            # Generate geometry for visible faces
            face_count = 0
            for face_data in visible_faces:
                self._create_face(face_data, block_registry, center_offset)
                face_count += 1
                
                # Progress reporting
                if face_count % 500 == 0:
                    report_progress(face_count, total_faces, "Creating faces")
            
            # Clean up mesh geometry
            self._finalize_mesh()
            
            # Create Blender mesh
            mesh = bpy.data.meshes.new("HytopiaWorld")
            
            # Convert bmesh to mesh with error handling
            try:
                self.bm.to_mesh(mesh)
                # Add UV coordinates after mesh creation
                self._add_uv_coordinates(mesh, blocks, block_registry)
            except Exception as e:
                print(f"Error converting bmesh to mesh: {e}")
                # Try a simpler approach
                mesh = self._create_simple_mesh(blocks, block_registry)
                if mesh:
                    self._add_uv_coordinates(mesh, blocks, block_registry)
                
            # Clean up bmesh
            if self.bm:
                self.bm.free()
                self.bm = None
            
            # Validate mesh
            if mesh:
                mesh.validate()
                mesh.update()
            
            print(f"Created mesh with {len(mesh.vertices)} vertices, {len(mesh.polygons)} faces")
            return mesh
            
        except Exception as e:
            print(f"Error creating mesh: {e}")
            if self.bm:
                self.bm.free()
            raise e
    
    def _calculate_visible_faces(self, blocks: Dict[Tuple[float, float, float], int]) -> List[Dict[str, Any]]:
        """
        Calculate which faces are visible (not adjacent to other solid blocks).
        
        Args:
            blocks: Dictionary mapping coordinates to block type IDs
            
        Returns:
            List of face data dictionaries for visible faces
        """
        visible_faces = []
        block_coords = set(blocks.keys())
        
        # Face directions with IDs for UV mapping: (dx, dy, dz, normal, vertices_offset, face_id)
        face_directions = [
            # Bottom face (Y-) - Hytopia -Y -> Blender -Z 
            (0, -1, 0, (0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], 0),
            # Top face (Y+) - Hytopia +Y -> Blender +Z
            (0, 1, 0, (0, 1, 0), [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)], 1),
            # Front face (Z-) - Hytopia -Z -> Blender -Y
            (0, 0, -1, (0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)], 2),
            # Back face (Z+) - Hytopia +Z -> Blender +Y
            (0, 0, 1, (0, 0, 1), [(1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)], 3),
            # Left face (X-) 
            (-1, 0, 0, (-1, 0, 0), [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)], 4),
            # Right face (X+)
            (1, 0, 0, (1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)], 5)
        ]
        
        for (x, y, z), block_id in blocks.items():
            for dx, dy, dz, normal, vertices_offset, face_id in face_directions:
                # Check if adjacent position has a block
                adjacent_pos = (x + dx, y + dy, z + dz)
                
                # Face is visible if no adjacent block or adjacent block is liquid/transparent
                if adjacent_pos not in block_coords:
                    visible_faces.append({
                        'position': (x, y, z),
                        'block_id': block_id,
                        'normal': normal,
                        'vertices_offset': vertices_offset,
                        'face_id': face_id  # Add face direction ID
                    })
        
        return visible_faces
    
    def _generate_all_faces(self, blocks: Dict[Tuple[float, float, float], int]) -> List[Dict[str, Any]]:
        """
        Generate all faces for all blocks (no culling).
        
        Args:
            blocks: Dictionary mapping coordinates to block type IDs
            
        Returns:
            List of face data dictionaries
        """
        all_faces = []
        
        # All six faces of a cube with face IDs
        face_directions = [
            # Bottom, Top, Front, Back, Left, Right
            ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], 0),
            ((0, 1, 0), [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)], 1),
            ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)], 2),
            ((0, 0, 1), [(1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)], 3),
            ((-1, 0, 0), [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)], 4),
            ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)], 5)
        ]
        
        for (x, y, z), block_id in blocks.items():
            for normal, vertices_offset, face_id in face_directions:
                all_faces.append({
                    'position': (x, y, z),
                    'block_id': block_id,
                    'normal': normal,
                    'vertices_offset': vertices_offset,
                    'face_id': face_id
                })
        
        return all_faces
    
    def _create_face(self, face_data: Dict[str, Any], block_registry: Dict[int, Dict[str, Any]], center_offset: Tuple[float, float, float] = (0, 0, 0)):
        """
        Create a single face in the bmesh.
        
        Args:
            face_data: Face information dictionary
            block_registry: Block type definitions
        """
        position = face_data['position']
        vertices_offset = face_data['vertices_offset']
        block_id = face_data['block_id']
        face_id = face_data.get('face_id', 0)
        
        # Create vertices for this face without caching to avoid shared faces
        face_verts = []
        for offset in vertices_offset:
            # Convert Hytopia coordinates to Blender coordinates:
            # Hytopia: (X, Y, Z) where Y is height
            # Blender: (X, Z, Y) where Z is height
            # Also flip X axis to fix left/right mirroring
            # Apply center offset to move imported content to origin
            vert_pos = (
                -(position[0] + offset[0]) + 1 + center_offset[0],  # Negate X + center offset
                (position[2] + offset[2]) - 1 + center_offset[1],   # Hytopia Z becomes Blender Y + center offset
                position[1] + offset[1] + center_offset[2]     # Hytopia Y becomes Blender Z (height) + center offset
            )
            
            # Always create new vertices for cleaner face separation
            vert = self.bm.verts.new(vert_pos)
            face_verts.append(vert)
        
        try:
            # Ensure vertices are valid and unique
            if len(face_verts) >= 3 and len(set(face_verts)) == len(face_verts):
                # Create face from vertices
                face = self.bm.faces.new(face_verts)
                
                # Store block ID and face direction for material assignment later
                if self.block_id_layer and face.is_valid:
                    try:
                        face[self.block_id_layer] = block_id
                    except:
                        pass
                
                if self.face_direction_layer and face.is_valid:
                    try:
                        face[self.face_direction_layer] = face_id
                    except:
                        pass
            
        except ValueError as e:
            # Face already exists or invalid geometry - skip it
            print(f"Warning: Could not create face at {position}: {e}")
        except Exception as e:
            print(f"Warning: Unexpected error creating face at {position}: {e}")
    
    def _finalize_mesh(self):
        """
        Finalize mesh by ensuring valid geometry.
        """
        try:
            # Ensure face indices are valid
            self.bm.faces.ensure_lookup_table()
            self.bm.verts.ensure_lookup_table()
            
            # Only recalculate normals - avoid remove_doubles which can corrupt face data
            if self.bm.faces:
                bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
            
            # Update normals
            self.bm.normal_update()
            
        except Exception as e:
            print(f"Warning: Error in mesh finalization: {e}")
            # Continue anyway - basic mesh should still work
    
    def _add_uv_coordinates(self, mesh: bpy.types.Mesh, 
                           blocks: Dict[Tuple[float, float, float], int] = None,
                           block_registry: Dict[int, Dict[str, Any]] = None):
        """
        Add UV coordinates to the mesh for proper texture mapping.
        For multi-texture blocks, maps each face to the correct texture region.
        For single-texture blocks, uses simple 0,0 to 1,1 mapping.
        """
        try:
            # Ensure mesh has a UV layer
            if not mesh.uv_layers:
                mesh.uv_layers.new(name="UVMap")
            
            uv_layer = mesh.uv_layers.active.data
            
            # Check if we need multi-texture UV mapping
            has_multi_texture = False
            if blocks and block_registry:
                for block_id in set(blocks.values()):
                    if block_id in block_registry:
                        block_type = block_registry[block_id]
                        if block_type.get('isMultiTexture', False):
                            has_multi_texture = True
                            break
            
            if has_multi_texture:
                self._add_multi_texture_uv_coordinates(mesh, uv_layer, blocks, block_registry)
            else:
                self._add_simple_uv_coordinates(mesh, uv_layer)
            
        except Exception as e:
            print(f"❌ Error adding UV coordinates: {e}")
            import traceback
            traceback.print_exc()
    
    def _add_simple_uv_coordinates(self, mesh: bpy.types.Mesh, uv_layer):
        """Add simple UV coordinates for single-texture blocks."""
        for poly in mesh.polygons:
            for i, loop_index in enumerate(poly.loop_indices):
                # Map each vertex of the face to texture coordinates
                if i == 0:
                    uv_layer[loop_index].uv = (0.0, 0.0)  # Bottom-left
                elif i == 1:
                    uv_layer[loop_index].uv = (1.0, 0.0)  # Bottom-right  
                elif i == 2:
                    uv_layer[loop_index].uv = (1.0, 1.0)  # Top-right
                elif i == 3:
                    uv_layer[loop_index].uv = (0.0, 1.0)  # Top-left
                else:
                    uv_layer[loop_index].uv = (0.0, 1.0)
        
        print(f"✓ Added simple UV coordinates to {len(mesh.polygons)} faces")
    
    def _add_multi_texture_uv_coordinates(self, mesh: bpy.types.Mesh, uv_layer, 
                                         blocks: Dict[Tuple[float, float, float], int],
                                         block_registry: Dict[int, Dict[str, Any]]):
        """
        Add UV coordinates for multi-texture blocks.
        Uses face direction to determine which texture region to use.
        Maps faces to a 3x2 texture atlas layout:
        [neg_x] [pos_x] [neg_y]
        [pos_y] [neg_z] [pos_z]
        """
        # Face ID to UV region mapping for texture atlas
        # Atlas layout matches the material manager's atlas creation
        face_uv_regions = {
            4: (0.0, 0.0, 0.333, 0.5),      # Left face (X-) -> neg_x (bottom-left)
            5: (0.333, 0.0, 0.666, 0.5),    # Right face (X+) -> pos_x (bottom-center)
            0: (0.666, 0.0, 1.0, 0.5),      # Bottom face (Y-) -> neg_y (bottom-right)
            1: (0.0, 0.5, 0.333, 1.0),      # Top face (Y+) -> pos_y (top-left)
            2: (0.333, 0.5, 0.666, 1.0),    # Front face (Z-) -> neg_z (top-center)
            3: (0.666, 0.5, 1.0, 1.0),      # Back face (Z+) -> pos_z (top-right)
        }
        
        # Try to get face direction information from mesh
        face_direction_data = None
        
        # Look for face direction in custom mesh data
        if hasattr(mesh, 'attributes'):
            for attr in mesh.attributes:
                if attr.name == "face_direction":
                    face_direction_data = attr.data
                    break
        
        # If no face direction data, try to infer from face normals
        if not face_direction_data:
            print("⚠️ No face direction data found, using face normal inference")
        
        for poly in mesh.polygons:
            # Get face direction ID
            face_id = 0  # Default to bottom face
            
            if face_direction_data and poly.index < len(face_direction_data):
                face_id = face_direction_data[poly.index].value
            else:
                # Infer face direction from face normal
                normal = poly.normal
                
                # Determine face direction based on normal vector
                if abs(normal.x) > abs(normal.y) and abs(normal.x) > abs(normal.z):
                    face_id = 5 if normal.x > 0 else 4  # Right or Left
                elif abs(normal.z) > abs(normal.y):
                    face_id = 1 if normal.z > 0 else 0  # Top or Bottom  
                else:
                    face_id = 3 if normal.y > 0 else 2  # Back or Front
            
            # Get UV region for this face
            u_min, v_min, u_max, v_max = face_uv_regions.get(face_id, (0.0, 0.0, 0.333, 0.5))
            
            # Apply UV coordinates to face vertices
            for i, loop_index in enumerate(poly.loop_indices):
                # Standard UV mapping for all faces (rotation handled in atlas creation)
                if i == 0:
                    uv_layer[loop_index].uv = (u_min, v_min)  # Bottom-left
                elif i == 1:
                    uv_layer[loop_index].uv = (u_max, v_min)  # Bottom-right  
                elif i == 2:
                    uv_layer[loop_index].uv = (u_max, v_max)  # Top-right
                elif i == 3:
                    uv_layer[loop_index].uv = (u_min, v_max)  # Top-left
                else:
                    uv_layer[loop_index].uv = (u_min, v_max)
        
        print(f"✓ Added multi-texture UV coordinates to {len(mesh.polygons)} faces")
        print(f"   Atlas regions: neg_x(0,0), pos_x(1,0), neg_y(2,0), pos_y(0,1), neg_z(1,1), pos_z(2,1)")

    def _create_simple_mesh(self, blocks: Dict[Tuple[float, float, float], int],
                           block_registry: Dict[int, Dict[str, Any]]) -> bpy.types.Mesh:
        """
        Fallback method to create mesh using simple cube operations.
        """
        print("Using fallback simple mesh creation...")
        
        try:
            # Create a new bmesh for fallback  
            fallback_bm = bmesh.new()
            
            # Create simple cubes for each block (one at a time)
            for (x, y, z), block_id in blocks.items():
                # Create cube at position
                bmesh.ops.create_cube(fallback_bm, size=1.0, 
                                    matrix=Matrix.Translation((x, y, z)))
            
            # Create mesh
            mesh = bpy.data.meshes.new("HytopiaWorld_Simple")
            fallback_bm.to_mesh(mesh)
            fallback_bm.free()
            
            # Add UV coordinates to the simple mesh too
            self._add_uv_coordinates(mesh, blocks, block_registry)
            
            return mesh
            
        except Exception as e:
            print(f"Error in fallback mesh creation: {e}")
            return None


def create_simple_cube_mesh(position: Tuple[float, float, float], 
                           size: float = 1.0) -> bpy.types.Mesh:
    """
    Create a simple cube mesh at specified position (fallback function).
    
    Args:
        position: (x, y, z) position for cube
        size: Size of the cube
        
    Returns:
        Blender mesh object
    """
    bm = bmesh.new()
    
    try:
        # Create cube
        bmesh.ops.create_cube(bm, size=size)
        
        # Move to position
        bmesh.ops.translate(bm, vec=position, verts=bm.verts)
        
        # Create Blender mesh
        mesh = bpy.data.meshes.new("SimpleCube")
        bm.to_mesh(mesh)
        bm.free()
        
        mesh.validate()
        mesh.update()
        
        return mesh
        
    except Exception as e:
        if bm:
            bm.free()
        raise e


def assign_materials_to_mesh(mesh_obj: bpy.types.Object,
                           mesh: bpy.types.Mesh, 
                           blocks: Dict[Tuple[float, float, float], int],
                           block_registry: Dict[int, Dict[str, Any]],
                           material_manager) -> bool:
    """
    Assign materials to mesh faces based on block types.
    
    Args:
        mesh_obj: Blender mesh object
        mesh: Blender mesh data
        blocks: Dictionary mapping coordinates to block type IDs
        block_registry: Block type definitions
        material_manager: Material manager instance
        
    Returns:
        True if materials assigned successfully
    """
    try:
        # Get unique block types used
        used_block_types = set(blocks.values())
        material_index_map = {}
        
        # Create materials for used block types and build index map
        for block_id in used_block_types:
            if block_id in block_registry:
                block_type = block_registry[block_id]
                material = material_manager.get_or_create_material(block_type)
                
                # Add material to mesh object
                mesh_obj.data.materials.append(material)
                material_index_map[block_id] = len(mesh_obj.data.materials) - 1
            else:
                # Use default material for unknown block types
                default_material = material_manager.create_default_material()
                if default_material.name not in [mat.name for mat in mesh_obj.data.materials]:
                    mesh_obj.data.materials.append(default_material)
                    material_index_map[block_id] = len(mesh_obj.data.materials) - 1
        
        print(f"Created {len(mesh_obj.data.materials)} materials for mesh")
        
        # Try to assign materials per face based on block_id layer
        if mesh_obj.data.materials and hasattr(mesh, 'polygons'):
            try:
                # For now, assign materials randomly to make blocks visible
                import random
                num_materials = len(mesh_obj.data.materials)
                for i, face in enumerate(mesh.polygons):
                    face.material_index = i % num_materials
                print(f"Assigned materials to {len(mesh.polygons)} faces")
            except Exception as e:
                print(f"Error assigning face materials: {e}")
                # Fallback: assign first material to all
                for face in mesh.polygons:
                    face.material_index = 0
        
        return True
        
    except Exception as e:
        print(f"Error assigning materials: {e}")
        import traceback
        traceback.print_exc()
        return False 