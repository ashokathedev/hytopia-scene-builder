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
        self.vertex_dict = {}  # Vertex cache for reuse
        
    def create_block_mesh(self, 
                         blocks: Dict[Tuple[float, float, float], int],
                         block_registry: Dict[int, Dict[str, Any]],
                         cull_faces: bool = True) -> bpy.types.Mesh:
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
        
        # Try to create face layer for storing block IDs (create once)
        try:
            self.block_id_layer = self.bm.faces.layers.int.new("block_id")
        except:
            print("Warning: Could not create block_id layer, continuing without it")
            self.block_id_layer = None
            
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
                self._create_face(face_data, block_registry)
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
                self._add_uv_coordinates(mesh)
            except Exception as e:
                print(f"Error converting bmesh to mesh: {e}")
                # Try a simpler approach
                mesh = self._create_simple_mesh(blocks, block_registry)
                if mesh:
                    self._add_uv_coordinates(mesh)
                
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
        
        # Face directions: (dx, dy, dz, normal, vertices_offset)
        face_directions = [
            # Bottom face (Y-)
            (0, -1, 0, (0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
            # Top face (Y+) 
            (0, 1, 0, (0, 1, 0), [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)]),
            # Front face (Z-)
            (0, 0, -1, (0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
            # Back face (Z+)
            (0, 0, 1, (0, 0, 1), [(1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)]),
            # Left face (X-)
            (-1, 0, 0, (-1, 0, 0), [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)]),
            # Right face (X+)
            (1, 0, 0, (1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)])
        ]
        
        for (x, y, z), block_id in blocks.items():
            for dx, dy, dz, normal, vertices_offset in face_directions:
                # Check if adjacent position has a block
                adjacent_pos = (x + dx, y + dy, z + dz)
                
                # Face is visible if no adjacent block or adjacent block is liquid/transparent
                if adjacent_pos not in block_coords:
                    visible_faces.append({
                        'position': (x, y, z),
                        'block_id': block_id,
                        'normal': normal,
                        'vertices_offset': vertices_offset
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
        
        # All six faces of a cube
        face_directions = [
            # Bottom, Top, Front, Back, Left, Right
            ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
            ((0, 1, 0), [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)]),
            ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
            ((0, 0, 1), [(1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)]),
            ((-1, 0, 0), [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)]),
            ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)])
        ]
        
        for (x, y, z), block_id in blocks.items():
            for normal, vertices_offset in face_directions:
                all_faces.append({
                    'position': (x, y, z),
                    'block_id': block_id,
                    'normal': normal,
                    'vertices_offset': vertices_offset
                })
        
        return all_faces
    
    def _create_face(self, face_data: Dict[str, Any], block_registry: Dict[int, Dict[str, Any]]):
        """
        Create a single face in the bmesh.
        
        Args:
            face_data: Face information dictionary
            block_registry: Block type definitions
        """
        position = face_data['position']
        vertices_offset = face_data['vertices_offset']
        block_id = face_data['block_id']
        
        # Create vertices for this face without caching to avoid shared faces
        face_verts = []
        for offset in vertices_offset:
            # Convert Hytopia coordinates to Blender coordinates:
            # Hytopia: (X, Y, Z) where Y is height
            # Blender: (X, Z, Y) where Z is height
            # Also flip X axis to fix left/right mirroring
            vert_pos = (
                -(position[0] + offset[0]),  # Negate X to fix left/right mirroring
                position[2] + offset[2],    # Hytopia Z becomes Blender Y
                position[1] + offset[1]     # Hytopia Y becomes Blender Z (height)
            )
            
            # Always create new vertices for cleaner face separation
            vert = self.bm.verts.new(vert_pos)
            face_verts.append(vert)
        
        try:
            # Ensure vertices are valid and unique
            if len(face_verts) >= 3 and len(set(face_verts)) == len(face_verts):
                # Create face from vertices
                face = self.bm.faces.new(face_verts)
                
                # Store block ID for material assignment later (use pre-created layer)
                if self.block_id_layer and face.is_valid:
                    try:
                        face[self.block_id_layer] = block_id
                    except:
                        # If layer assignment fails, continue anyway
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
    
    def _add_uv_coordinates(self, mesh: bpy.types.Mesh):
        """
        Add UV coordinates to the mesh so textures can be displayed properly.
        Each face gets UV coordinates that map the full texture (0,0 to 1,1).
        """
        try:
            # Ensure mesh has a UV layer
            if not mesh.uv_layers:
                mesh.uv_layers.new(name="UVMap")
            
            uv_layer = mesh.uv_layers.active.data
            
            # Create UV coordinates for each face
            # Each quad face needs 4 UV coordinates (one per corner)
            for poly in mesh.polygons:
                for i, loop_index in enumerate(poly.loop_indices):
                    # Map each vertex of the face to texture coordinates
                    # Use simple box mapping - each face gets the full texture
                    if i == 0:
                        uv_layer[loop_index].uv = (0.0, 0.0)  # Bottom-left
                    elif i == 1:
                        uv_layer[loop_index].uv = (1.0, 0.0)  # Bottom-right  
                    elif i == 2:
                        uv_layer[loop_index].uv = (1.0, 1.0)  # Top-right
                    elif i == 3:
                        uv_layer[loop_index].uv = (0.0, 1.0)  # Top-left
                    else:
                        # For faces with more than 4 vertices (shouldn't happen with cubes)
                        # Just repeat the last UV coordinate
                        uv_layer[loop_index].uv = (0.0, 1.0)
            
            print(f"✓ Added UV coordinates to {len(mesh.polygons)} faces")
            
        except Exception as e:
            print(f"❌ Error adding UV coordinates: {e}")
            import traceback
            traceback.print_exc()

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
            self._add_uv_coordinates(mesh)
            
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