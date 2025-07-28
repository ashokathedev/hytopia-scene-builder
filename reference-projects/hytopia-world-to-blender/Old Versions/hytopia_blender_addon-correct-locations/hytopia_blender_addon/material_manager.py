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
        
        # Handle special properties (AFTER texture setup)
        # Temporarily disable liquid properties for water blocks
        # if block_type.get('isLiquid', False):
        #     self._setup_liquid_material(material, bsdf_node, texture_loaded)
        
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