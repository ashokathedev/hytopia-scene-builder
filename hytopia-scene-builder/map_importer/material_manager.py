"""
Material and texture management for Hytopia blocks
"""
import os
import bpy
from typing import Dict, Optional, Any
from .utils import validate_texture_path, safe_name


class HytopiaMaterialManager:
    """
    Manages creation and caching of materials for Hytopia blocks.
    
    Handles texture loading with fallback options and material caching
    to avoid creating duplicate materials.
    """
    
    def __init__(self, texture_base_path: str = ""):
        self.texture_base_path = texture_base_path
        self.material_cache: Dict[str, bpy.types.Material] = {}
        self.missing_textures: set = set()  # Track missing textures to avoid repeated warnings
        
    def set_texture_base_path(self, path: str):
        """Set the base path for texture files."""
        self.texture_base_path = path
        
    def get_or_create_material(self, block_type: Dict[str, Any]) -> bpy.types.Material:
        """
        Get existing material or create new one for block type.
        
        Args:
            block_type: Block type data from Hytopia map
            
        Returns:
            Blender material object
        """
        block_name = block_type.get('name', 'unknown')
        material_name = f"hytopia_{safe_name(block_name)}"
        
        # Return cached material if exists
        if material_name in self.material_cache:
            return self.material_cache[material_name]
        
        # Check if material already exists in Blender
        if material_name in bpy.data.materials:
            material = bpy.data.materials[material_name]
            self.material_cache[material_name] = material
            return material
        
        # Create new material
        material = self._create_material(block_type, material_name)
        self.material_cache[material_name] = material
        
        return material
    
    def _create_material(self, block_type: Dict[str, Any], material_name: str) -> bpy.types.Material:
        """
        Create a new Blender material using MCprep-style approach.
        
        Args:
            block_type: Block type data from Hytopia map
            material_name: Name for the new material
            
        Returns:
            New Blender material
        """
        # Check if this is a multi-texture block
        is_multi_texture = block_type.get('isMultiTexture', False)
        
        if is_multi_texture:
            return self._create_multi_texture_material(block_type, material_name)
        else:
            return self._create_single_texture_material(block_type, material_name)
    
    def _create_single_texture_material(self, block_type: Dict[str, Any], material_name: str) -> bpy.types.Material:
        """
        Create a single-texture material (original logic).
        
        Args:
            block_type: Block type data from Hytopia map
            material_name: Name for the new material
            
        Returns:
            New Blender material
        """
        # Create material
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True
        
        # Get material nodes
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        # Clear ALL default nodes (like MCprep does)
        nodes.clear()
        
        # Create nodes in MCprep style
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        output_node.location = (800, 0)
        
        bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf_node.location = (400, 0)
        
        # Connect BSDF to output
        links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
        
        # Set specular IOR to 0 for all materials
        self._set_specular_ior_to_zero(bsdf_node)
        
        # Handle texture
        texture_uri = block_type.get('textureUri', '')
        texture_loaded = False
        if texture_uri and self.texture_base_path:
            texture_loaded = self._setup_texture_nodes(material, bsdf_node, texture_uri, block_type)
            if not texture_loaded:
                # Fallback to colored material if texture fails
                self._setup_color_material(material, bsdf_node, block_type)
        else:
            # No texture URI or no base path - create colored material
            self._setup_color_material(material, bsdf_node, block_type)
        
        return material
    
    def _set_specular_ior_to_zero(self, bsdf_node: bpy.types.ShaderNode):
        """
        Set the Specular IOR Level to 0 for the given Principled BSDF node.
        
        Args:
            bsdf_node: The Principled BSDF node to modify
        """
        try:
            # Set Specular IOR Level to 0
            if 'Specular IOR Level' in bsdf_node.inputs:
                bsdf_node.inputs['Specular IOR Level'].default_value = 0.0
            # Also set Specular to 0 for older Blender versions
            if 'Specular' in bsdf_node.inputs:
                bsdf_node.inputs['Specular'].default_value = 0.0
        except Exception as e:
            print(f"Warning: Could not set specular IOR to 0: {e}")
    
    def _create_multi_texture_material(self, block_type: Dict[str, Any], material_name: str) -> bpy.types.Material:
        """
        Create a multi-texture material for blocks with different textures per face.
        Uses UV mapping to select the correct texture for each face.
        
        Args:
            block_type: Block type data from Hytopia map
            material_name: Name for the new material
            
        Returns:
            New Blender material
        """
        print(f"🎨 Creating multi-texture material: {material_name}")
        
        # Create material
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True
        
        # Get material nodes
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        # Clear default nodes
        nodes.clear()
        
        # Create output node
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        output_node.location = (1200, 0)
        
        # Create BSDF node
        bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf_node.location = (800, 0)
        
        # Connect BSDF to output
        links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
        
        # Set specular IOR to 0 for all materials
        self._set_specular_ior_to_zero(bsdf_node)
        
        # Load face textures and create the multi-texture node setup
        texture_loaded = self._setup_multi_texture_nodes(material, bsdf_node, block_type)
        
        if not texture_loaded:
            # Fallback to colored material if textures fail
            self._setup_color_material(material, bsdf_node, block_type)
        
        return material
    
    def _setup_texture_nodes(self, material: bpy.types.Material, 
                           bsdf_node: bpy.types.ShaderNode,
                           texture_uri: str,
                           block_type: Dict[str, Any]) -> bool:
        """
        Setup texture nodes for material using MCprep approach.
        
        Args:
            material: Blender material
            bsdf_node: Principled BSDF node
            texture_uri: Relative texture path from block type
            block_type: Block type data
            
        Returns:
            True if texture was successfully loaded and connected
        """
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        # Validate texture path
        texture_path = validate_texture_path(texture_uri, self.texture_base_path)
        
        # Only show debug info if texture not found
        debug_texture_loading = not (texture_path and os.path.exists(texture_path))
        if debug_texture_loading:
            print(f"🔍 Texture Debug for {material.name}:")
            print(f"   TextureURI: {texture_uri}")
            print(f"   Base Path: {self.texture_base_path}")
            print(f"   Resolved: {texture_path}")
            print(f"   Exists: {bool(texture_path and os.path.exists(texture_path))}")
        
        if not texture_path or not os.path.exists(texture_path):
            # Texture not found
            if texture_uri not in self.missing_textures:
                print(f"❌ Texture not found: {texture_uri}")
                self.missing_textures.add(texture_uri)
            return False
        
        # Load image using MCprep approach
        try:
            image = bpy.data.images.load(texture_path, check_existing=True)
            print(f"✓ Loaded texture: {os.path.basename(texture_path)} ({image.size[0]}x{image.size[1]})")
        except Exception as e:
            print(f"❌ Failed to load texture {texture_path}: {e}")
            return False
        
        # Verify image loaded properly
        if image.size[0] == 0 or image.size[1] == 0:
            print(f"❌ Image has invalid size: {image.size}")
            return False
            
        # Check if image has pixel data
        try:
            # Force image to load pixel data
            image.pixels[:4]  # Try to access first 4 pixel values
            print(f"✓ Image has pixel data: {len(image.pixels)} pixels")
        except Exception as e:
            print(f"❌ Image has no pixel data: {e}")
            try:
                # Try to reload the image
                image.reload()
                print(f"✓ Reloaded image, now has {len(image.pixels)} pixels")
            except Exception as reload_e:
                print(f"❌ Failed to reload image: {reload_e}")
                return False
        
        # Create texture node (MCprep style)
        try:
            image_node = nodes.new(type='ShaderNodeTexImage')
            image_node.name = "Diffuse Texture"
            image_node.label = "Diffuse Texture"  
            image_node.location = (0, 0)  # Place before BSDF
            image_node.interpolation = 'Closest'  # Pixelated look
            image_node.image = image
            
            # Connect directly to BSDF (simple approach)
            links.new(image_node.outputs['Color'], bsdf_node.inputs['Base Color'])
            links.new(image_node.outputs['Alpha'], bsdf_node.inputs['Alpha'])
            
            # Debug node connections
            print(f"✓ Created texture node with image: {image.name}")
            print(f"   Node has image: {image_node.image is not None}")
            print(f"   Connected to BSDF Base Color: {len(bsdf_node.inputs['Base Color'].links) > 0}")
            print(f"   Material uses nodes: {material.use_nodes}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to create texture nodes: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _setup_multi_texture_nodes(self, material: bpy.types.Material,
                                  bsdf_node: bpy.types.ShaderNode,
                                  block_type: Dict[str, Any]) -> bool:
        """
        Setup multi-texture nodes for cube faces using texture atlas.
        Creates a single atlas image with all 6 face textures arranged in a 3x2 grid.
        
        Args:
            material: Blender material
            bsdf_node: Principled BSDF node
            block_type: Block type data
            
        Returns:
            True if texture atlas was successfully created
        """
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        texture_uri = block_type.get('textureUri', '')
        if not texture_uri or not self.texture_base_path:
            return False
        
        # Define face mappings with coordinate conversion
        # Fixed mapping based on user feedback:
        # - +y face in blender was showing +z content, so swap these
        # - +x face in blender was showing -z content, so swap these
        face_mappings = {
            'neg_x': '+y.png',    # Left face (X-) TOP FACE
            'pos_x': '-x.png',    # Right face (X+) - was showing -z content, so give it -z texture
            'neg_y': '+x.png',    # Bottom face (Hytopia -Y -> Blender -Z) gets +y.png
            'pos_y': '+z.png',    # Top face (Hytopia +Y -> Blender +Z) - was showing +z content, so give it +z texture
            'neg_z': '-z.png',    # Front face (Hytopia -Z -> Blender -Y) - now gets +x texture
            'pos_z': '-y.png'     # Back face (Hytopia +Z -> Blender +Y) - now gets -y texture
        }
        
        # Define rotation mappings for each face (0, 90, 180, 270 degrees)
        # You can adjust these values to fix orientation issues
        face_rotations = {
            'neg_x': 270,      # Left face - no rotation TOP FACE
            'pos_x': 270,      # Right face - no rotation  
            'neg_y': 270,      # Bottom face - no rotation
            'pos_y': 270,      # Top face - no rotation
            'neg_z': 270,      # Front face - no rotation
            'pos_z': 270       # Back face - no rotation
        }
        
        # Create texture atlas with rotation info
        atlas_image = self._create_texture_atlas(block_type, face_mappings, face_rotations)
        if not atlas_image:
            print("❌ Failed to create texture atlas")
            return False
        
        # Create simple image texture node with atlas
        image_node = nodes.new(type='ShaderNodeTexImage')
        image_node.name = "Multi_Texture_Atlas"
        image_node.label = "Multi Texture Atlas"
        image_node.location = (0, 0)
        image_node.interpolation = 'Closest'  # Pixelated look
        image_node.image = atlas_image
        
        # Create UV Map node
        uv_node = nodes.new(type='ShaderNodeUVMap')
        uv_node.location = (-200, -100)
        
        # Connect UV to image texture
        links.new(uv_node.outputs['UV'], image_node.inputs['Vector'])
        
        # Connect texture to BSDF
        links.new(image_node.outputs['Color'], bsdf_node.inputs['Base Color'])
        links.new(image_node.outputs['Alpha'], bsdf_node.inputs['Alpha'])
        
        print(f"✓ Created multi-texture atlas material for {material.name}")
        return True
    
    def _create_texture_atlas(self, block_type: Dict[str, Any], 
                             face_mappings: Dict[str, str],
                             face_rotations: Dict[str, int]) -> Optional[bpy.types.Image]:
        """
        Create a texture atlas by combining 6 face textures into a single image.
        Atlas layout (3x2 grid):
        [neg_x] [pos_x] [neg_y]
        [pos_y] [neg_z] [pos_z]
        
        Args:
            block_type: Block type data
            face_mappings: Mapping of face names to texture filenames
            face_rotations: Mapping of face names to rotation degrees (0, 90, 180, 270)
            
        Returns:
            Blender image with combined textures, or None if failed
        """
        texture_uri = block_type.get('textureUri', '')
        texture_dir = os.path.join(self.texture_base_path, texture_uri)
        block_name = block_type.get('name', 'unknown')
        
        # Load all face images
        face_images = {}
        texture_size = 16  # Default minecraft texture size
        
        for face, filename in face_mappings.items():
            texture_path = os.path.join(texture_dir, filename)
            if os.path.exists(texture_path):
                try:
                    image = bpy.data.images.load(texture_path, check_existing=True)
                    face_images[face] = image
                    # Get texture size from first loaded image
                    if len(face_images) == 1:
                        texture_size = max(image.size[0], image.size[1]) 
                    print(f"✓ Loaded {face} texture: {filename} ({image.size[0]}x{image.size[1]})")
                except Exception as e:
                    print(f"❌ Failed to load {face} texture {filename}: {e}")
            else:
                print(f"❌ Texture not found: {texture_path}")
        
        if len(face_images) == 0:
            print("❌ No face textures loaded for atlas")
            return None
        
        # Create atlas image (3x2 grid)
        atlas_width = texture_size * 3
        atlas_height = texture_size * 2
        atlas_name = f"atlas_{safe_name(block_name)}"
        
        # Check if atlas already exists
        if atlas_name in bpy.data.images:
            return bpy.data.images[atlas_name]
        
        # Create new atlas image
        atlas_image = bpy.data.images.new(atlas_name, atlas_width, atlas_height, alpha=True)
        
        # Atlas layout positions
        atlas_positions = {
            'neg_x': (0, 1),           # Bottom-left
            'pos_x': (1, 1),           # Bottom-center  
            'neg_y': (2, 1),           # Bottom-right
            'pos_y': (0, 0),           # Top-left
            'neg_z': (1, 0),           # Top-center
            'pos_z': (2, 0)            # Top-right
        }
        
        # Initialize atlas pixels (RGBA)
        atlas_pixels = [0.0] * (atlas_width * atlas_height * 4)
        
        # Copy face textures to atlas
        for face, (grid_x, grid_y) in atlas_positions.items():
            if face in face_images:
                face_image = face_images[face]
                rotation = face_rotations.get(face, 0)
                
                # Force image to load pixels
                face_image.pixels[:]  # This forces pixel data to load
                
                # Get rotated pixels
                face_pixels = self._get_rotated_pixels(face_image, rotation, texture_size)
                
                # Calculate position in atlas
                start_x = grid_x * texture_size
                start_y = grid_y * texture_size
                
                # Copy rotated pixels from face image to atlas
                for y in range(texture_size):
                    for x in range(texture_size):
                        # Source pixel index in rotated face pixels
                        face_idx = (y * texture_size + x) * 4
                        
                        # Destination pixel index in atlas
                        atlas_x = start_x + x
                        atlas_y = start_y + y
                        atlas_idx = (atlas_y * atlas_width + atlas_x) * 4
                        
                        # Copy RGBA values
                        if face_idx + 3 < len(face_pixels) and atlas_idx + 3 < len(atlas_pixels):
                            atlas_pixels[atlas_idx:atlas_idx+4] = face_pixels[face_idx:face_idx+4]
            else:
                # Fill missing texture with magenta (debug color)
                start_x = atlas_positions[face][0] * texture_size
                start_y = atlas_positions[face][1] * texture_size
                
                for y in range(texture_size):
                    for x in range(texture_size):
                        atlas_x = start_x + x
                        atlas_y = start_y + y
                        atlas_idx = (atlas_y * atlas_width + atlas_x) * 4
                        
                        if atlas_idx + 3 < len(atlas_pixels):
                            atlas_pixels[atlas_idx:atlas_idx+4] = [1.0, 0.0, 1.0, 1.0]  # Magenta
        
        # Apply pixels to atlas image
        atlas_image.pixels[:] = atlas_pixels
        
        print(f"✓ Created texture atlas: {atlas_name} ({atlas_width}x{atlas_height})")
        return atlas_image
    
    def _get_rotated_pixels(self, image: bpy.types.Image, rotation: int, size: int) -> list:
        """
        Get rotated pixel data from an image.
        
        Args:
            image: Source image
            rotation: Rotation in degrees (0, 90, 180, 270)
            size: Expected texture size (will crop/pad if different)
            
        Returns:
            List of rotated RGBA pixel values
        """
        # Get original pixels
        original_pixels = list(image.pixels)
        img_width, img_height = image.size
        
        # Create output pixel array
        rotated_pixels = [0.0] * (size * size * 4)
        
        if rotation == 0:
            # No rotation - just copy (with resize if needed)
            for y in range(min(size, img_height)):
                for x in range(min(size, img_width)):
                    src_idx = (y * img_width + x) * 4
                    dst_idx = (y * size + x) * 4
                    if src_idx + 3 < len(original_pixels):
                        rotated_pixels[dst_idx:dst_idx+4] = original_pixels[src_idx:src_idx+4]
        
        elif rotation == 90:
            # 90 degrees clockwise: (x,y) -> (size-1-y, x)
            for y in range(min(size, img_height)):
                for x in range(min(size, img_width)):
                    src_idx = (y * img_width + x) * 4
                    new_x = size - 1 - y
                    new_y = x
                    dst_idx = (new_y * size + new_x) * 4
                    if src_idx + 3 < len(original_pixels) and dst_idx + 3 < len(rotated_pixels):
                        rotated_pixels[dst_idx:dst_idx+4] = original_pixels[src_idx:src_idx+4]
        
        elif rotation == 180:
            # 180 degrees: (x,y) -> (size-1-x, size-1-y)
            for y in range(min(size, img_height)):
                for x in range(min(size, img_width)):
                    src_idx = (y * img_width + x) * 4
                    new_x = size - 1 - x
                    new_y = size - 1 - y
                    dst_idx = (new_y * size + new_x) * 4
                    if src_idx + 3 < len(original_pixels) and dst_idx + 3 < len(rotated_pixels):
                        rotated_pixels[dst_idx:dst_idx+4] = original_pixels[src_idx:src_idx+4]
        
        elif rotation == 270:
            # 270 degrees clockwise (90 counter-clockwise): (x,y) -> (y, size-1-x)
            for y in range(min(size, img_height)):
                for x in range(min(size, img_width)):
                    src_idx = (y * img_width + x) * 4
                    new_x = y
                    new_y = size - 1 - x
                    dst_idx = (new_y * size + new_x) * 4
                    if src_idx + 3 < len(original_pixels) and dst_idx + 3 < len(rotated_pixels):
                        rotated_pixels[dst_idx:dst_idx+4] = original_pixels[src_idx:src_idx+4]
        
        else:
            # Invalid rotation - use original
            for y in range(min(size, img_height)):
                for x in range(min(size, img_width)):
                    src_idx = (y * img_width + x) * 4
                    dst_idx = (y * size + x) * 4
                    if src_idx + 3 < len(original_pixels):
                        rotated_pixels[dst_idx:dst_idx+4] = original_pixels[src_idx:src_idx+4]
        
        return rotated_pixels
    
    def _setup_color_material(self, material: bpy.types.Material,
                            bsdf_node: bpy.types.ShaderNode,
                            block_type: Dict[str, Any]):
        """
        Setup colored material (no texture).
        
        Args:
            material: Blender material
            bsdf_node: Principled BSDF node 
            block_type: Block type data
        """
        # Generate color based on block name hash
        block_name = block_type.get('name', 'default')
        color = self._generate_color_from_name(block_name)
        
        bsdf_node.inputs['Base Color'].default_value = (*color, 1.0)
        
    def _setup_fallback_material(self, material: bpy.types.Material,
                               bsdf_node: bpy.types.ShaderNode,
                               block_type: Dict[str, Any]):
        """
        Setup fallback material when texture loading fails.
        
        Args:
            material: Blender material
            bsdf_node: Principled BSDF node
            block_type: Block type data
        """
        # Create colored material as fallback
        block_name = block_type.get('name', 'default')
        color = self._generate_color_from_name(block_name)
        
        bsdf_node.inputs['Base Color'].default_value = (*color, 1.0)
        
        # Add slight roughness to distinguish from textured materials
        bsdf_node.inputs['Roughness'].default_value = 0.8
    
    def _setup_liquid_material(self, material: bpy.types.Material,
                             bsdf_node: bpy.types.ShaderNode,
                             texture_loaded: bool):
        """
        Setup liquid material properties.
        
        Args:
            material: Blender material
            bsdf_node: Principled BSDF node
            texture_loaded: Whether a texture was successfully loaded
        """
        if texture_loaded:
            # Apply liquid properties to textured material
            bsdf_node.inputs['Transmission'].default_value = 0.9
            bsdf_node.inputs['Alpha'].default_value = 0.7
            bsdf_node.inputs['Roughness'].default_value = 0.1
            
            # Enable blend mode for transparency
            material.blend_method = 'BLEND'
            material.show_transparent_back = True
        else:
            # Create basic liquid material without texture
            bsdf_node.inputs['Base Color'].default_value = (0.2, 0.6, 1.0, 0.7)  # Blue water
            bsdf_node.inputs['Transmission'].default_value = 0.9
            bsdf_node.inputs['Alpha'].default_value = 0.7
            bsdf_node.inputs['Roughness'].default_value = 0.1
            
            # Enable blend mode for transparency
            material.blend_method = 'BLEND'
            material.show_transparent_back = True
    
    def _generate_color_from_name(self, name: str) -> tuple:
        """
        Generate a consistent color from block name.
        
        Args:
            name: Block name
            
        Returns:
            RGB color tuple
        """
        # Simple hash-based color generation
        hash_val = hash(name) % 0xFFFFFF
        r = ((hash_val >> 16) & 0xFF) / 255.0
        g = ((hash_val >> 8) & 0xFF) / 255.0  
        b = (hash_val & 0xFF) / 255.0
        
        # Ensure colors are not too dark
        r = max(0.3, r)
        g = max(0.3, g)
        b = max(0.3, b)
        
        return (r, g, b)
    
    def create_default_material(self) -> bpy.types.Material:
        """
        Create a default material for unknown block types.
        
        Returns:
            Default Blender material
        """
        material_name = "hytopia_default"
        
        if material_name in bpy.data.materials:
            return bpy.data.materials[material_name]
        
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True
        
        # Set to magenta to make missing materials obvious
        bsdf = material.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (1.0, 0.0, 1.0, 1.0)  # Magenta
            
        return material
    
    def clear_cache(self):
        """Clear material cache (useful for testing)."""
        self.material_cache.clear()
        self.missing_textures.clear()
        
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about cached materials.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'cached_materials': len(self.material_cache),
            'missing_textures': len(self.missing_textures)
        } 