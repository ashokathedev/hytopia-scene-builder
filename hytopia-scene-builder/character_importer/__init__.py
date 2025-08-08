bl_info = {
    "name": "Hytopia Character Importer",
    "author": "Hytopia Community",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > N Panel > Hytopia",
    "description": "Import Hytopia player characters with customizable texture layering system",
    "warning": "",
    "doc_url": "https://github.com/hytopiagg/assets",
    "category": "Import-Export",
}

import bpy
import os
import tempfile
import urllib.request
import shutil
import json
import re
import subprocess
import sys
from bpy.props import StringProperty, BoolProperty, IntProperty, EnumProperty, FloatVectorProperty
from bpy.types import Operator, Panel, PropertyGroup, Menu
from bpy_extras.io_utils import ImportHelper

# Auto-install PIL if not available
def ensure_pil_installed():
    """Ensure PIL/Pillow is installed, install if necessary"""
    try:
        from PIL import Image
        print("PIL/Pillow already available")
        return True
    except ImportError:
        print("PIL/Pillow not found, attempting to install...")
        try:
            # Get the python executable used by Blender
            python_exe = sys.executable
            
            # First try to upgrade pip to avoid warnings
            try:
                subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pip"], 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Pip updated successfully")
            except Exception as e:
                print(f"Pip update failed (non-critical): {e}")
            
            # Install Pillow with better error handling
            try:
                # Try with --user flag for better compatibility
                subprocess.check_call([python_exe, "-m", "pip", "install", "--user", "Pillow"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Pillow installed with --user flag")
            except Exception as e:
                print(f"User installation failed, trying system install: {e}")
                # Fallback to system install
                subprocess.check_call([python_exe, "-m", "pip", "install", "Pillow"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Pillow installed system-wide")
            
            # Force reload of sys.path to find newly installed packages
            import site
            site.main()
            
            # Add user site packages to sys.path if not already there
            user_site = site.getusersitepackages()
            if user_site not in sys.path:
                sys.path.insert(0, user_site)
                print(f"Added user site packages: {user_site}")
            
            # Try importing again with multiple attempts
            for attempt in range(3):
                try:
                    from PIL import Image
                    print("PIL/Pillow successfully installed and imported")
                    return True
                except ImportError:
                    if attempt < 2:
                        print(f"Import attempt {attempt + 1} failed, retrying...")
                        import importlib
                        importlib.invalidate_caches()
                        
                        # Try to find Pillow in common locations
                        import glob
                        possible_paths = [
                            os.path.join(user_site, "PIL"),
                            os.path.join(user_site, "Pillow*"),
                            os.path.join(sys.prefix, "Lib", "site-packages", "PIL"),
                            os.path.join(sys.prefix, "Lib", "site-packages", "Pillow*")
                        ]
                        
                        for path_pattern in possible_paths:
                            matches = glob.glob(path_pattern)
                            for match in matches:
                                if match not in sys.path:
                                    sys.path.insert(0, match)
                                    print(f"Added potential PIL path: {match}")
                    else:
                        raise ImportError("PIL import failed after installation")
            
        except Exception as e:
            print(f"Failed to install PIL/Pillow: {e}")
            print("Texture compositing will be disabled. You can manually install Pillow:")
            print("1. Open Blender's Python console (Window > Toggle System Console)")
            print("2. Run: import subprocess; subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow'])")
            print("3. Restart Blender after installation")
            return False

def composite_character_texture(textures, cache_dir, import_id):
    """Composite multiple texture layers into a single PNG using PIL"""
    try:
        # Check if composite already exists for this character
        composite_filename = f"character_composite_{import_id}.png"
        existing_composite = os.path.join(cache_dir, composite_filename)
        if os.path.exists(existing_composite):
            print(f"Using existing composite texture: {composite_filename}")
            return existing_composite
        
        # Ensure PIL is available
        if not ensure_pil_installed():
            print("Cannot composite textures without PIL")
            print("Falling back to simple texture application...")
            return None
        
        from PIL import Image
        
        print("Starting texture composition...")
        
        # Start with a transparent base image (assuming 64x64 character texture)
        # We'll get the size from the first available texture
        base_size = (64, 64)  # Default size
        composite = None
        
        # Layer order: Skin → Eye Base → Pupil → Clothing → Hair  
        layer_order = ['skin', 'eye_base', 'pupil', 'clothing', 'hair']
        
        for layer_name in layer_order:
            if layer_name in textures and textures[layer_name] and os.path.exists(textures[layer_name]):
                print(f"  Adding {layer_name} layer: {os.path.basename(textures[layer_name])}")
                
                try:
                    # Load the texture
                    layer_img = Image.open(textures[layer_name]).convert('RGBA')
                    
                    # Initialize composite with first layer size
                    if composite is None:
                        base_size = layer_img.size
                        composite = Image.new('RGBA', base_size, (0, 0, 0, 0))
                        print(f"  Base texture size: {base_size}")
                    
                    # Resize layer to match base size if needed
                    if layer_img.size != base_size:
                        layer_img = layer_img.resize(base_size, Image.NEAREST)
                    
                    # Composite the layer using alpha blending
                    composite = Image.alpha_composite(composite, layer_img)
                    print(f"  Successfully added {layer_name} layer")
                    
                except Exception as e:
                    print(f"  Failed to add {layer_name} layer: {e}")
        
        if composite is None:
            print("No valid textures to composite")
            return None
        
        # Save the composited texture with unique naming
        output_path = os.path.join(cache_dir, f"character_composite_{import_id}.png")
        composite.save(output_path, "PNG")
        print(f"Saved composite texture: {output_path}")
        print(f"Composite texture size: {composite.size}")
        
        return output_path
        
    except Exception as e:
        print(f"Failed to composite textures: {e}")
        return None

# Static fallback items that are always available
SKIN_FALLBACK_ITEMS = [('default', 'Default', 'Default skin')]
CLOTHING_FALLBACK_ITEMS = [('none', 'None', 'No clothing')]
EYES_FALLBACK_ITEMS = [('none', 'None', 'No eyes')]
HAIR_STYLE_FALLBACK_ITEMS = [('8', 'Style 8', 'Hair style 8')]
HAIR_COLOR_FALLBACK_ITEMS = [('brown', 'Brown', 'Brown hair')]

# Global cache for texture options - initialized with fallback items
texture_options_cache = {
    'skin': SKIN_FALLBACK_ITEMS.copy(),
    'clothing': CLOTHING_FALLBACK_ITEMS.copy(),
    'eyes': EYES_FALLBACK_ITEMS.copy(),
    'hair_styles': HAIR_STYLE_FALLBACK_ITEMS.copy(),
    'hair_colors': HAIR_COLOR_FALLBACK_ITEMS.copy()
}

def get_github_directory_contents(path):
    """Get directory contents from GitHub API"""
    try:
        url = f"https://api.github.com/repos/hytopiagg/assets/contents/{path}"
        print(f"Fetching: {url}")
        
        # Add headers to avoid rate limiting
        headers = {
            'User-Agent': 'Hytopia-Character-Importer/1.0'
        }
        
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode())
        
        print(f"Found {len(data)} items in {path}")
        for item in data:
            print(f"  - {item['name']} ({item['type']})")
        
        return data
    except Exception as e:
        print(f"Failed to fetch directory contents for {path}: {e}")
        return []

def update_texture_options():
    """Update texture options from the Hytopia repository"""
    global texture_options_cache
    
    try:
        print("Starting texture options update...")
        
        # Get skin options
        print("Fetching skin textures...")
        skin_contents = get_github_directory_contents("release/models/players/Textures/skin-texture")
        skin_options = [('default', 'Default', 'Default skin')]
        for item in skin_contents:
            if item['type'] == 'file' and item['name'].endswith('.png'):
                skin_name = item['name'].replace('.png', '')
                # Format the name nicely (e.g., "skin-tone-1" -> "Skin Tone 1")
                display_name = skin_name.replace('-', ' ').title()
                skin_options.append((skin_name, display_name, f'{display_name} skin'))
        texture_options_cache['skin'] = skin_options
        print(f"Found {len(skin_options)} skin options")
        
        # Get clothing options - clothing is in numbered folders
        print("Fetching clothing textures...")
        clothing_contents = get_github_directory_contents("release/models/players/Textures/clothing-texture")
        clothing_options = [('none', 'None', 'No clothing')]
        for item in clothing_contents:
            if item['type'] == 'dir':
                try:
                    clothing_num = int(item['name'])
                    clothing_options.append((str(clothing_num), f'Style {clothing_num}', f'Clothing style {clothing_num}'))
                except ValueError:
                    continue
        texture_options_cache['clothing'] = clothing_options
        print(f"Found {len(clothing_options)} clothing options")
        
        # Get eyes options
        print("Fetching eye textures...")
        eyes_contents = get_github_directory_contents("release/models/players/Textures/eye-texture")
        eyes_options = [('none', 'None', 'No eyes')]
        for item in eyes_contents:
            if item['type'] == 'file' and item['name'].endswith('.png'):
                eyes_name = item['name'].replace('.png', '')
                # Format the name nicely
                display_name = eyes_name.replace('-', ' ').title()
                eyes_options.append((eyes_name, display_name, f'{display_name} eyes'))
        texture_options_cache['eyes'] = eyes_options
        print(f"Found {len(eyes_options)} eye options")
        
        # Get hair styles
        print("Fetching hair styles...")
        hair_styles_contents = get_github_directory_contents("release/models/players/Textures/hairstyle-texture")
        hair_styles = []
        for item in hair_styles_contents:
            if item['type'] == 'dir':
                try:
                    style_num = int(item['name'])
                    hair_styles.append(style_num)
                except ValueError:
                    continue
        hair_style_options = []
        for style in sorted(hair_styles):
            hair_style_options.append((str(style), f'Style {style}', f'Hair style {style}'))
        texture_options_cache['hair_styles'] = hair_style_options if hair_style_options else [('1', 'Style 1', 'Hair style 1')]
        print(f"Found {len(hair_style_options)} hair styles")
        
        # Get hair colors for first available style
        if hair_styles:
            first_style = hair_styles[0]
            print(f"Fetching hair colors for style {first_style}...")
            hair_colors_contents = get_github_directory_contents(f"release/models/players/Textures/hairstyle-texture/{first_style}")
            hair_colors = []
            for item in hair_colors_contents:
                if item['type'] == 'file' and item['name'].endswith('.png'):
                    color_name = item['name'].replace('.png', '')
                    # Extract color number from filename like "hair-1-3.png" -> "3"
                    color_parts = color_name.split('-')
                    if len(color_parts) >= 3:
                        color_num = color_parts[-1]
                        hair_colors.append((color_name, f'Color {color_num}', f'Hair color {color_num}'))
            texture_options_cache['hair_colors'] = hair_colors if hair_colors else [('brown', 'Brown', 'Brown hair')]
            print(f"Found {len(hair_colors)} hair colors")
        
        print("Texture options updated successfully")
        return True
        
    except Exception as e:
        print(f"Failed to update texture options: {e}")
        return False

# Callback functions for dynamic EnumProperty items
def get_skin_items(self, context):
    """Get skin texture options dynamically"""
    try:
        items = texture_options_cache.get('skin', SKIN_FALLBACK_ITEMS)
        # Ensure all items are valid tuples with 3 strings
        validated_items = []
        for item in items:
            if isinstance(item, tuple) and len(item) >= 3:
                validated_items.append((str(item[0]), str(item[1]), str(item[2])))
        
        # Ensure default item is always present
        if validated_items and not any(item[0] == 'default' for item in validated_items):
            validated_items.insert(0, ('default', 'Default', 'Default skin'))
        
        return validated_items if validated_items else SKIN_FALLBACK_ITEMS
    except Exception as e:
        print(f"Error in get_skin_items: {e}")
        return SKIN_FALLBACK_ITEMS

def get_clothing_items(self, context):
    """Get clothing texture options dynamically"""
    try:
        items = texture_options_cache.get('clothing', CLOTHING_FALLBACK_ITEMS)
        validated_items = []
        for item in items:
            if isinstance(item, tuple) and len(item) >= 3:
                validated_items.append((str(item[0]), str(item[1]), str(item[2])))
        
        # Ensure default item is always present
        if validated_items and not any(item[0] == 'none' for item in validated_items):
            validated_items.insert(0, ('none', 'None', 'No clothing'))
        
        return validated_items if validated_items else CLOTHING_FALLBACK_ITEMS
    except Exception as e:
        print(f"Error in get_clothing_items: {e}")
        return CLOTHING_FALLBACK_ITEMS

def get_eyes_items(self, context):
    """Get eyes texture options dynamically"""
    try:
        items = texture_options_cache.get('eyes', EYES_FALLBACK_ITEMS)
        validated_items = []
        for item in items:
            if isinstance(item, tuple) and len(item) >= 3:
                validated_items.append((str(item[0]), str(item[1]), str(item[2])))
        
        # Ensure default item is always present
        if validated_items and not any(item[0] == 'none' for item in validated_items):
            validated_items.insert(0, ('none', 'None', 'No eyes'))
        
        return validated_items if validated_items else EYES_FALLBACK_ITEMS
    except Exception as e:
        print(f"Error in get_eyes_items: {e}")
        return EYES_FALLBACK_ITEMS

def get_hair_style_items(self, context):
    """Get hair style options dynamically"""
    try:
        items = texture_options_cache.get('hair_styles', HAIR_STYLE_FALLBACK_ITEMS)
        validated_items = []
        for item in items:
            if isinstance(item, tuple) and len(item) >= 3:
                validated_items.append((str(item[0]), str(item[1]), str(item[2])))
        
        # Ensure default item is always present
        if validated_items and not any(item[0] == '3' for item in validated_items):
            validated_items.insert(0, ('3', 'Style 3', 'Hair style 3'))
        
        return validated_items if validated_items else HAIR_STYLE_FALLBACK_ITEMS
    except Exception as e:
        print(f"Error in get_hair_style_items: {e}")
        return HAIR_STYLE_FALLBACK_ITEMS

def get_hair_color_items(self, context):
    """Get hair color options dynamically"""
    try:
        items = texture_options_cache.get('hair_colors', HAIR_COLOR_FALLBACK_ITEMS)
        validated_items = []
        for item in items:
            if isinstance(item, tuple) and len(item) >= 3:
                validated_items.append((str(item[0]), str(item[1]), str(item[2])))
        
        # Ensure default item is always present
        if validated_items and not any(item[0] == 'brown' for item in validated_items):
            validated_items.insert(0, ('brown', 'Brown', 'Brown hair'))
        
        return validated_items if validated_items else HAIR_COLOR_FALLBACK_ITEMS
    except Exception as e:
        print(f"Error in get_hair_color_items: {e}")
        return HAIR_COLOR_FALLBACK_ITEMS

# Properties for the add-on
class HytopiaProperties(PropertyGroup):
    """Properties for Hytopia Character Importer"""
    
    # URL for the player model
    player_url: StringProperty(
        name="Player Model URL",
        description="URL to the Hytopia player GLTF model",
        default="https://raw.githubusercontent.com/hytopiagg/assets/main/release/models/players/player.gltf"
    )
    
    # Texture repository URL
    textures_url: StringProperty(
        name="Textures URL",
        description="Base URL for Hytopia textures",
        default="https://raw.githubusercontent.com/hytopiagg/assets/main/release/models/players/Textures"
    )
    
    # Import animations option
    import_animations: BoolProperty(
        name="Include Default Animations",
        description="Include animations from the GLTF file",
        default=True
    )
    
    # Skin texture method selection
    skin_method: EnumProperty(
        name="Skin Method",
        description="Choose how to apply skin texture to the character",
        items=[
            ('DEFAULT', 'Default Skin', 'Use the default skin baked into the GLTF model'),
            ('SELECT', 'Select Skin Options', 'Choose from available Hytopia skin options'),
            ('CUSTOM', 'Upload Custom Skin', 'Use your own custom skin texture file')
        ],
        default='DEFAULT'
    )
    
    # Custom skin texture file path
    custom_skin_path: StringProperty(
        name="Custom Skin File",
        description="Path to your custom skin texture file (PNG format recommended)",
        default="",
        subtype='FILE_PATH'
    )
    
    # Hair type for custom skin method
    custom_hair_type: StringProperty(
        name="Hair Type",
        description="Selected hair type for custom skin method",
        default="8"
    )
    
    # Character customization options - using simple string properties
    skin_type: StringProperty(
        name="Skin Type",
        description="Selected skin texture type",
        default="default"
    )
    
    clothing_type: StringProperty(
        name="Clothing",
        description="Selected clothing style",
        default="none"
    )
    
    eye_type: StringProperty(
        name="Eyes",
        description="Selected eye style",
        default="none"
    )
    
    hair_style: StringProperty(
        name="Hair Style",
        description="Selected hair style",
        default="8"
    )
    
    hair_color: StringProperty(
        name="Hair Color",
        description="Selected hair color",
        default="brown"
    )
    
    # Eye color for selections method
    eye_color: FloatVectorProperty(
        name="Eye Color",
        description="Color for character eyes (Selections method only)",
        default=(0.5, 0.3, 0.1, 1.0),  # Nice brown default
        size=4,
        subtype='COLOR',
        min=0.0,
        max=1.0
    )

class HYTOPIA_OT_ImportPlayer(Operator):
    """Append rigged Hytopia Character and apply textures/masks"""
    bl_idname = "hytopia.import_player"
    bl_label = "Import Hytopia Player"
    bl_description = "Download and import the Hytopia player model with custom texture layering"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        """Execute the import operation using .blend append"""
        props = context.scene.hytopia_props
        try:
            # Create unique directory for this import instance
            import_id = f"hytopia_character_{len(bpy.data.objects):04d}"
            addon_dir = os.path.dirname(__file__)
            addon_root = os.path.dirname(addon_dir)
            cache_dir = os.path.join(addon_dir, "texture_cache", import_id)
            os.makedirs(cache_dir, exist_ok=True)

            # Resolve .blend path (try in addon root first, then project root)
            possible_blend_paths = [
                os.path.join(addon_root, "hytopia-character.blend"),
                os.path.join(os.path.dirname(addon_root), "hytopia-character.blend"),
            ]
            blend_path = None
            for p in possible_blend_paths:
                if os.path.exists(p):
                    blend_path = p
                    break
            if not blend_path:
                raise Exception("Could not find hytopia-character.blend in addon or project root")

            print(f"Using blend file: {blend_path}")

            # Track existing objects
            existing_objects = set(bpy.context.scene.objects)

            # Append the collection "Hytopia Character"
            collection_dir = os.path.join(blend_path, "Collection") + os.sep
            print(f"Appending collection from: {collection_dir}")
            bpy.ops.wm.append(directory=collection_dir, filename="Hytopia Character", link=False)

            # Ensure collection is linked to scene
            appended_collection = bpy.data.collections.get("Hytopia Character")
            if appended_collection:
                scene_child_names = [c.name for c in bpy.context.scene.collection.children]
                if appended_collection.name not in scene_child_names:
                    bpy.context.scene.collection.children.link(appended_collection)
                print("Linked appended collection to the scene")

            # Gather newly added objects
            new_objects = list(set(bpy.context.scene.objects) - existing_objects)
            if not new_objects and appended_collection:
                # Fallback: collect objects from the appended collection
                new_objects = [obj for obj in appended_collection.all_objects]

            if not new_objects:
                raise Exception("No objects were appended from the blend file")

            print(f"Appended {len(new_objects)} objects from collection 'Hytopia Character'")

            # Ensure objects are accessible under the scene via the linked collection (no per-object relinking necessary)

            # Rename imported objects to be unique for this character
            self.rename_imported_objects(new_objects, import_id)

            # Find the primary mesh (the one holding hair vertex groups)
            primary_mesh = self.find_primary_mesh(new_objects)
            if not primary_mesh:
                print("Warning: Could not locate primary character mesh with hair groups. Using first mesh as fallback.")
                primary_candidates = [o for o in new_objects if o.type == 'MESH']
                primary_mesh = primary_candidates[0] if primary_candidates else None
            if not primary_mesh:
                raise Exception("No mesh objects found in appended collection")
            print(f"Primary character mesh: {primary_mesh.name}")

            # Collect target meshes
            target_meshes = [o for o in new_objects if o.type == 'MESH']

            # Apply method-specific actions
            if props.skin_method == 'DEFAULT':
                # Do not modify materials; only reduce specular on all materials and set hair masks to style 8
                self.apply_default_skin(target_meshes, import_id)
                self.apply_hair_masks_for_method(primary_mesh, props, default_style=8)
                self.report({'INFO'}, f"Hytopia character appended with default materials (hair 8). ID: {import_id}")
            elif props.skin_method == 'SELECT':
                # Build composite and apply to the primary mesh
                print("Building composite for selections...")
                self.apply_layered_textures(props, cache_dir, import_id, target_meshes)
                self.apply_hair_masks_for_method(primary_mesh, props)
                self.report({'INFO'}, f"Hytopia character appended with selected textures. ID: {import_id}")
            elif props.skin_method == 'CUSTOM':
                # Load and apply custom texture to the primary mesh
                print("Applying custom skin texture...")
                self.apply_custom_skin(props, cache_dir, import_id, target_meshes)
                self.apply_hair_masks_for_method(primary_mesh, props, is_custom=True)
                self.report({'INFO'}, f"Hytopia character appended with custom texture. ID: {import_id}")

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            return {'CANCELLED'}

    def find_primary_mesh(self, objects):
        """Return the mesh object that contains hair vertex groups, or None"""
        hair_regex = re.compile(r"(?:^|\b)hair-(\d{1,4})(?:[-_].*)?$", re.IGNORECASE)
        for obj in objects:
            if obj.type != 'MESH' or not obj.data or not obj.vertex_groups:
                continue
            for vg in obj.vertex_groups:
                if hair_regex.match(vg.name):
                    print(f"Found primary mesh candidate: {obj.name} via group {vg.name}")
                    return obj
        return None

    def _find_principled_node(self, material):
        if not material or not material.use_nodes:
            return None
        for node in material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                return node
        return None

    def _pick_image_texture_node(self, material, principled_node):
        """Pick the most likely image texture node driving Base Color.
        Preference order:
        1) TEX_IMAGE directly linked to Principled Base Color
        2) TEX_IMAGE named/labelled 'BASE COLOR'
        3) First TEX_IMAGE in node tree
        """
        if not material or not material.use_nodes:
            return None
        nodes = material.node_tree.nodes
        # 1) direct link to Principled Base Color
        if principled_node and 'Base Color' in principled_node.inputs:
            base_input = principled_node.inputs['Base Color']
            for link in base_input.links:
                if link.from_node and link.from_node.type == 'TEX_IMAGE':
                    return link.from_node
        # 2) by name/label
        for node in nodes:
            if node.type == 'TEX_IMAGE':
                name = (node.name or '').lower()
                label = (node.label or '').lower()
                if 'base color' in name or 'base color' in label:
                    return node
        # 3) first TEX_IMAGE
        for node in nodes:
            if node.type == 'TEX_IMAGE':
                return node
        return None

    def _ensure_alpha_clip(self, material):
        try:
            material.blend_method = 'CLIP'
            material.shadow_method = 'CLIP'
        except Exception:
            pass

    def set_image_on_existing_material(self, material, image, import_id):
        """Swap the image on the existing Image Texture node. Create one if none exists."""
        if not material:
            return False
        if not material.use_nodes:
            material.use_nodes = True
        principled = self._find_principled_node(material)
        if principled is None:
            return False
        # Set specular to 0 where available
        try:
            if 'Specular IOR Level' in principled.inputs:
                principled.inputs['Specular IOR Level'].default_value = 0.0
            if 'Specular' in principled.inputs:
                principled.inputs['Specular'].default_value = 0.0
        except Exception:
            pass
        tex = self._pick_image_texture_node(material, principled)
        if tex is None:
            # Create a new one and wire it minimally to Base Color and Alpha
            tex = material.node_tree.nodes.new(type='ShaderNodeTexImage')
            tex.location = (-600, 300)
            tex.name = f"Character_Texture_{import_id}"
            # Link
            try:
                material.node_tree.links.new(tex.outputs['Color'], principled.inputs['Base Color'])
                if 'Alpha' in principled.inputs:
                    material.node_tree.links.new(tex.outputs['Alpha'], principled.inputs['Alpha'])
            except Exception:
                pass
        # Assign image and sampling settings
        if image is not None:
            tex.image = image
        try:
            tex.interpolation = 'Closest'
        except Exception:
            pass
        self._ensure_alpha_clip(material)
        return True

    def apply_image_to_mesh(self, mesh_obj, image, import_id):
        """Set the provided image on all materials of the mesh, reusing the existing node setup."""
        if mesh_obj.type != 'MESH' or not mesh_obj.data or not mesh_obj.data.materials:
            return
        for mat in mesh_obj.data.materials:
            self.set_image_on_existing_material(mat, image, import_id)

    def group_hair_vertex_groups(self, mesh_obj):
        """Map hair style number (int) to a list of vertex group names belonging to that style"""
        mapping = {}
        hair_regex = re.compile(r"(?:^|\b)hair-(\d{1,4})(?:[-_].*)?$", re.IGNORECASE)
        for vg in mesh_obj.vertex_groups:
            m = hair_regex.match(vg.name)
            if not m:
                continue
            try:
                style_num = int(m.group(1))
            except ValueError:
                continue
            mapping.setdefault(style_num, []).append(vg.name)
        print(f"Hair vertex groups found: { {k: len(v) for k, v in mapping.items()} }")
        return mapping

    def clear_existing_hair_masks(self, mesh_obj):
        """Remove previously added hair Mask modifiers"""
        to_remove = [mod for mod in mesh_obj.modifiers if mod.type == 'MASK' and mod.name.startswith('HairMask')]
        for mod in to_remove:
            mesh_obj.modifiers.remove(mod)

    def build_union_vertex_group(self, mesh_obj, target_group_name, source_group_names):
        """Create a vertex group that is the union of all vertices in source_group_names"""
        # Remove existing target group if present
        existing = mesh_obj.vertex_groups.get(target_group_name)
        if existing:
            mesh_obj.vertex_groups.remove(existing)
        union_group = mesh_obj.vertex_groups.new(name=target_group_name)
        # Map source names to indices
        source_indices = []
        for name in source_group_names:
            vg = mesh_obj.vertex_groups.get(name)
            if vg:
                source_indices.append(vg.index)
        if not source_indices:
            return union_group
        # Build set of vertices that belong to any source group
        union_vertex_indices = set()
        # Ensure we evaluate on the evaluated depsgraph copy to get up-to-date groups
        for v in mesh_obj.data.vertices:
            for g in v.groups:
                if g.group in source_indices and g.weight > 0.0:
                    union_vertex_indices.add(v.index)
                    break
        if union_vertex_indices:
            union_group.add(list(union_vertex_indices), 1.0, 'REPLACE')
        return union_group

    def reorder_mask_modifiers_before_armature(self, mesh_obj):
        """Ensure mask modifiers are evaluated before armature for correct hiding"""
        # Move all HairMask modifiers to the top in original order to ensure they run before Armature
        mask_names = [m.name for m in mesh_obj.modifiers if m.type == 'MASK' and m.name.startswith('HairMask')]
        for name in mask_names:
            try:
                idx = mesh_obj.modifiers.find(name)
                while idx > 0:
                    mesh_obj.modifiers.move(idx, idx - 1)
                    idx -= 1
            except Exception:
                pass

    def apply_hair_masks(self, mesh_obj, selected_style):
        """Hide hair vertex groups not matching the selected style using Mask modifiers"""
        if mesh_obj.type != 'MESH':
            return
        mapping = self.group_hair_vertex_groups(mesh_obj)
        if not mapping:
            print(f"No hair vertex groups found on {mesh_obj.name}")
            return
        self.clear_existing_hair_masks(mesh_obj)
        # Build a union of all non-selected hair groups
        non_selected_group_names = []
        for style_num, group_names in mapping.items():
            if style_num == selected_style:
                continue
            non_selected_group_names.extend(group_names)
        union_name = f"HairMaskUnion_Not_{selected_style:04d}"
        union_group = self.build_union_vertex_group(mesh_obj, union_name, non_selected_group_names)
        # Single mask to hide the union group
        mask = mesh_obj.modifiers.new(name=f"HairMask_{selected_style:04d}", type='MASK')
        mask.vertex_group = union_group.name
        mask.invert_vertex_group = True  # hide union, keep body + selected hair
        mask.show_viewport = True
        mask.show_render = True
        mask.show_in_editmode = True
        self.reorder_mask_modifiers_before_armature(mesh_obj)
        print(f"Applied hair mask using union group '{union_group.name}' (selected style {selected_style}) on {mesh_obj.name}")

    def apply_hair_masks_for_method(self, mesh_obj, props, default_style=None, is_custom=False):
        """Pick target hair style based on method and apply masks"""
        try:
            if default_style is not None and props.skin_method == 'DEFAULT':
                target_style = int(default_style)
            elif props.skin_method == 'SELECT':
                target_style = int(props.hair_style)
            elif props.skin_method == 'CUSTOM':
                target_style = int(props.custom_hair_type)
            else:
                target_style = int(default_style or 8)
        except Exception:
            target_style = int(default_style or 8)
        print(f"Applying hair masks for style {target_style} on {mesh_obj.name}")
        self.apply_hair_masks(mesh_obj, target_style)
    
    def rename_imported_objects(self, imported_objects, import_id):
        """Rename imported objects to be unique for this character instance"""
        try:
            print(f"Renaming {len(imported_objects)} imported objects for character {import_id}...")
            
            for obj in imported_objects:
                # Get the base name without Blender's automatic suffixes (.001, .002, etc.)
                base_name = obj.name.split('.')[0]
                
                # Create new unique name
                new_name = f"{base_name}_{import_id}"
                
                # Check if the new name already exists and make it unique if needed
                counter = 0
                final_name = new_name
                while final_name in bpy.data.objects:
                    counter += 1
                    final_name = f"{new_name}_{counter:03d}"
                
                # Rename the object
                old_name = obj.name
                obj.name = final_name
                print(f"  Renamed: {old_name} → {final_name}")
                
                # If it's a mesh object, also rename the mesh data
                if obj.type == 'MESH' and obj.data:
                    old_mesh_name = obj.data.name
                    obj.data.name = f"{final_name}_Mesh"
                    print(f"    Mesh data: {old_mesh_name} → {obj.data.name}")
                    
        except Exception as e:
            print(f"Error renaming objects: {e}")
    
    def rotate_imported_objects(self, imported_objects):
        """Rotate all imported objects 180 degrees around Z axis to fix orientation"""
        try:
            import math
            
            print(f"Rotating {len(imported_objects)} imported objects 180° around Z axis...")
            
            # 180 degrees in radians
            rotation_angle = math.radians(180)
            
            for obj in imported_objects:
                # Only rotate objects that have rotation (mesh, armature, etc.)
                if hasattr(obj, 'rotation_euler'):
                    # Get current rotation
                    current_rotation = obj.rotation_euler.copy()
                    
                    # Add 180 degrees to Z rotation
                    new_z_rotation = current_rotation.z + rotation_angle
                    
                    # Normalize to 0-2π range
                    while new_z_rotation > 2 * math.pi:
                        new_z_rotation -= 2 * math.pi
                    
                    # Apply new rotation
                    obj.rotation_euler.z = new_z_rotation
                    
                    print(f"  Rotated {obj.name}: Z rotation {math.degrees(current_rotation.z):.1f}° → {math.degrees(new_z_rotation):.1f}°")
                else:
                    print(f"  Skipped {obj.name}: no rotation_euler attribute")
            
            print(f"Rotation applied to {len(imported_objects)} objects")
            
        except Exception as e:
            print(f"Error rotating objects: {e}")
    
    def apply_default_skin(self, imported_objects, import_id):
        """Apply default skin method - just set specular values to 0, preserve existing textures"""
        try:
            # Filter imported objects to get only mesh objects
            target_objects = [obj for obj in imported_objects if obj.type == 'MESH']
            
            print(f"Applying default skin method to {len(target_objects)} mesh objects...")
            
            for mesh_obj in target_objects:
                print(f"  Processing mesh: {mesh_obj.name}")
                
                # Process all materials on this mesh
                if mesh_obj.data and mesh_obj.data.materials:
                    for mat_slot in mesh_obj.data.materials:
                        if mat_slot and mat_slot.use_nodes:
                            # Find Principled BSDF node
                            for node in mat_slot.node_tree.nodes:
                                if node.type == 'BSDF_PRINCIPLED':
                                    # Set specular values to 0
                                    try:
                                        if 'Specular IOR Level' in node.inputs:
                                            node.inputs['Specular IOR Level'].default_value = 0.0
                                        if 'Specular' in node.inputs:
                                            node.inputs['Specular'].default_value = 0.0
                                        print(f"    Set specular values to 0 for material: {mat_slot.name}")
                                    except Exception as e:
                                        print(f"    Warning: Could not set specular values for {mat_slot.name}: {e}")
                                    break
                else:
                    print(f"    No materials found on {mesh_obj.name}")
            
            print(f"Default skin method applied to {len(target_objects)} mesh objects")
            
        except Exception as e:
            print(f"Failed to apply default skin method: {e}")
    
    def apply_custom_skin(self, props, cache_dir, import_id, imported_objects):
        """Apply custom skin method - load and apply user-provided texture file"""
        try:
            # Validate custom skin path
            if not props.custom_skin_path:
                raise Exception("No custom skin file path provided")
            
            if not os.path.exists(props.custom_skin_path):
                raise Exception(f"Custom skin file not found: {props.custom_skin_path}")
            
            # Check file extension
            valid_extensions = ['.png', '.jpg', '.jpeg']
            file_ext = os.path.splitext(props.custom_skin_path)[1].lower()
            if file_ext not in valid_extensions:
                raise Exception(f"Unsupported file format: {file_ext}. Use PNG, JPG, or JPEG")
            
            # Filter imported objects to get only mesh objects
            target_objects = [obj for obj in imported_objects if obj.type == 'MESH']
            
            print(f"Applying custom skin from: {props.custom_skin_path}")
            print(f"Processing {len(target_objects)} mesh objects...")
            
            # Load the custom skin image once with unique name
            custom_image_name = f"Custom_Skin_{import_id}"
            
            # Check if image already exists in Blender
            existing_image = bpy.data.images.get(custom_image_name)
            if existing_image:
                print(f"Using existing custom image: {custom_image_name}")
                custom_image = existing_image
            else:
                # Load the custom image
                try:
                    abs_custom_path = os.path.abspath(props.custom_skin_path)
                    custom_image = bpy.data.images.load(abs_custom_path)
                    custom_image.name = custom_image_name
                    print(f"Loaded custom image: {custom_image_name}")
                except Exception as e:
                    raise Exception(f"Failed to load custom skin image: {e}")
            
            # Apply the custom image to all mesh objects
            for mesh_obj in target_objects:
                print(f"  Processing mesh: {mesh_obj.name}")
                self.apply_custom_to_mesh(mesh_obj, custom_image, import_id)
            
            print(f"Custom skin method applied to {len(target_objects)} mesh objects")
            
        except Exception as e:
            print(f"Failed to apply custom skin method: {e}")
            raise  # Re-raise to show error in UI
    
    def apply_custom_to_mesh(self, mesh_obj, custom_image, import_id):
        """Apply a custom skin image by swapping images on existing materials"""
        try:
            print(f"  Processing custom skin for mesh: {mesh_obj.name}")
            
            # Ensure we're in object mode
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.mode_set(mode='OBJECT')
            
            if custom_image:
                print(f"    Applying custom image: {custom_image.name}")
                self.apply_image_to_mesh(mesh_obj, custom_image, import_id)
                print(f"    Successfully applied custom skin to {mesh_obj.name}")
            else:
                print(f"    No custom image provided for {mesh_obj.name}")
                
        except Exception as e:
            print(f"Failed to apply custom skin to {mesh_obj.name}: {str(e)}")
    
    def manage_hair_visibility(self, imported_objects, props, import_id):
        """Backwards-compat: apply hair masks on a single-mesh character instead of toggling objects"""
        try:
            primary_mesh = self.find_primary_mesh(imported_objects)
            if not primary_mesh:
                print("No primary mesh with hair groups found for hair visibility")
                return
            self.apply_hair_masks_for_method(primary_mesh, props)
        except Exception as e:
            print(f"Failed to apply hair masks: {e}")
    
    def show_hair_hierarchy(self, hair_obj):
        """Show hair object and all its children"""
        try:
            # Show the object itself
            hair_obj.hide_viewport = False
            hair_obj.hide_render = False
            
            # Show all children recursively
            for child in hair_obj.children:
                child.hide_viewport = False
                child.hide_render = False
                self.show_hair_hierarchy(child)  # Recursive for nested children
                
        except Exception as e:
            print(f"Error showing hair hierarchy for {hair_obj.name}: {e}")
    
    def hide_hair_hierarchy(self, hair_obj):
        """Hide hair object and all its children"""
        try:
            # Hide the object itself
            hair_obj.hide_viewport = True
            hair_obj.hide_render = True
            
            # Hide all children recursively
            for child in hair_obj.children:
                child.hide_viewport = True
                child.hide_render = True
                self.hide_hair_hierarchy(child)  # Recursive for nested children
                
        except Exception as e:
            print(f"Error hiding hair hierarchy for {hair_obj.name}: {e}")
    
    def apply_layered_textures(self, props, cache_dir, import_id, imported_objects):
        """Apply layered textures to the imported model based on mesh names"""
        try:
            # Filter imported objects to get only mesh objects
            target_objects = [obj for obj in imported_objects if obj.type == 'MESH']
            
            print(f"Found {len(target_objects)} mesh objects total")
            for i, obj in enumerate(target_objects):
                print(f"  {i+1}. {obj.name} (materials: {len(obj.data.materials) if obj.data else 0})")
            
            if not target_objects:
                self.report({'WARNING'}, "No mesh objects found")
                return
            
            # Download textures based on selections
            textures = {}
            
            print(f"  Current selections:")
            print(f"    Skin: {props.skin_type}")
            print(f"    Clothing: {props.clothing_type}")
            print(f"    Eyes: {props.eye_type}")
            print(f"    Hair Style: {props.hair_style}")
            print(f"    Hair Color: {props.hair_color}")
            
            # Download skin texture
            if props.skin_type != 'default':
                print(f"  Downloading skin texture: {props.skin_type}")
                textures['skin'] = self.download_texture(f"skin-texture/{props.skin_type}.png", cache_dir)
            else:
                # Try the first available skin texture
                skin_options = texture_options_cache.get('skin', [])
                for skin_option in skin_options:
                    if skin_option[0] != 'default':
                        print(f"  Downloading default skin texture: {skin_option[0]}")
                        textures['skin'] = self.download_texture(f"skin-texture/{skin_option[0]}.png", cache_dir)
                        if textures['skin']:
                            break
            
            # Download clothing texture
            if props.clothing_type != 'none':
                print(f"  Downloading clothing texture: {props.clothing_type}")
                # Try different possible clothing texture paths
                clothing_paths = [
                    f"clothing-texture/{props.clothing_type}/clothing-{props.clothing_type}.png",
                    f"clothing-texture/clothing-{props.clothing_type}.png",
                    f"clothing-texture/{props.clothing_type}/clothing-texture.png",
                    f"clothing-texture/{props.clothing_type}.png"
                ]
                for path in clothing_paths:
                    result = self.download_texture(path, cache_dir)
                    if result:
                        textures['clothing'] = result
                        print(f"    Found clothing texture at: {path}")
                        break
                else:
                    print(f"    No clothing texture found for {props.clothing_type}")
            else:
                print(f"  Skipping clothing (none selected)")
            
            # Download eye base texture (always applied for compilation)
            print(f"  Downloading eye base texture")
            textures['eye_base'] = self.download_texture("eye-texture/eye-texture.png", cache_dir)
            
            # Download pupil texture (always applied for compilation, even though geometry uses solid color)
            print(f"  Downloading pupil texture for compilation")
            textures['pupil'] = self.download_texture("eye-texture/pupil-texture.png", cache_dir)
            
            
            # Download hair texture
            if props.hair_style != '8' or props.hair_color != 'brown':
                print(f"  Downloading hair texture: {props.hair_style}/{props.hair_color}")
                # Try different possible hair texture paths
                hair_paths = [
                    f"hairstyle-texture/{props.hair_style}/{props.hair_color}.png",
                    f"hairstyle-texture/{props.hair_style}/hair-{props.hair_style}-{props.hair_color.split('-')[-1] if '-' in props.hair_color else props.hair_color}.png"
                ]
                for path in hair_paths:
                    result = self.download_texture(path, cache_dir)
                    if result:
                        textures['hair'] = result
                        print(f"    Found hair texture at: {path}")
                        break
                else:
                    print(f"    No hair texture found for {props.hair_style}/{props.hair_color}")
            else:
                print(f"  Skipping hair (default selected)")
            
            print(f"  Downloaded textures: {list(textures.keys())}")
            for key, path in textures.items():
                if path:
                    print(f"    {key}: {os.path.basename(path)} (exists: {os.path.exists(path)})")
                else:
                    print(f"    {key}: None")
            
            # Create composite texture ONCE for this character
            print(f"Creating composite texture for character {import_id}...")
            composite_path = composite_character_texture(textures, cache_dir, import_id)
            
            if composite_path:
                # Load the composite image ONCE with unique name
                composite_image_name = f"Hytopia_Composite_{import_id}"
                
                # Check if image already exists in Blender
                existing_image = bpy.data.images.get(composite_image_name)
                if existing_image:
                    print(f"Using existing composite image: {composite_image_name}")
                    composite_image = existing_image
                else:
                    # Load the composite image
                    try:
                        abs_composite_path = os.path.abspath(composite_path)
                        composite_image = bpy.data.images.load(abs_composite_path)
                        composite_image.name = composite_image_name
                        print(f"Loaded composite image: {composite_image_name}")
                    except Exception as e:
                        print(f"Failed to load composite image: {e}")
                        self.report({'ERROR'}, f"Failed to load composite texture: {str(e)}")
                        return
                
                # Apply the same composite image to all mesh objects
                print(f"Applying composite texture to {len(target_objects)} mesh objects...")
                for i, mesh_obj in enumerate(target_objects):
                    print(f"  Processing mesh {i+1}/{len(target_objects)}: {mesh_obj.name}")
                    self.apply_composite_to_mesh(mesh_obj, composite_image, import_id)
                
                self.report({'INFO'}, f"Applied composite texture to {len(target_objects)} mesh objects")
            else:
                # Fallback: Apply individual textures without compositing
                print("Falling back to individual texture application...")
                self.apply_individual_textures(target_objects, textures, import_id)
                self.report({'WARNING'}, "Applied individual textures (compositing unavailable)")
            
        except Exception as e:
            self.report({'WARNING'}, f"Failed to apply textures: {str(e)}")
    
    def apply_individual_textures(self, mesh_objects, textures, import_id):
        """Apply individual textures to mesh objects without compositing"""
        try:
            print("Applying individual textures to mesh objects...")
            
            for mesh_obj in mesh_objects:
                print(f"Processing mesh object: {mesh_obj.name}")
                
                # Apply the first available texture to each mesh
                applied_texture = None
                for texture_type, texture_path in textures.items():
                    if texture_path and os.path.exists(texture_path):
                        print(f"  Applying {texture_type} texture: {os.path.basename(texture_path)}")
                        self.apply_simple_texture(mesh_obj, texture_path, import_id)
                        applied_texture = texture_path
                        break
                
                if not applied_texture:
                    print(f"  No valid textures found for {mesh_obj.name}")
            
            self.report({'INFO'}, f"Applied individual textures to {len(mesh_objects)} mesh objects")
            
        except Exception as e:
            print(f"Failed to apply individual textures: {e}")
            self.report({'WARNING'}, f"Failed to apply individual textures: {str(e)}")
    
    def apply_composite_to_mesh(self, mesh_obj, composite_image, import_id):
        """Apply a pre-loaded composite image to a mesh by swapping images in existing materials"""
        try:
            print(f"Processing mesh object: {mesh_obj.name}")
            
            # Check if this is a pupil object for Selections method
            is_pupil = ("pupil-left-geo" in mesh_obj.name.lower() or 
                       "pupil-right-geo" in mesh_obj.name.lower())
            
            # Ensure we're in object mode
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Apply material based on object type
            if is_pupil:
                # Apply solid eye color for pupil objects
                props = bpy.context.scene.hytopia_props
                print(f"  Applying solid eye color to pupil: {mesh_obj.name}")
                # Apply to all materials' Principled nodes
                for mat in mesh_obj.data.materials:
                    pn = self._find_principled_node(mat)
                    if pn and 'Base Color' in pn.inputs:
                        pn.inputs['Base Color'].default_value = props.eye_color
                print(f"  Applied eye color: {props.eye_color}")
            else:
                if composite_image:
                    print(f"  Applying composite image: {composite_image.name}")
                    self.apply_image_to_mesh(mesh_obj, composite_image, import_id)
                    print(f"  Successfully applied composite texture to {mesh_obj.name}")
                else:
                    print(f"  No composite image provided for {mesh_obj.name}")
            
        except Exception as e:
            print(f"Failed to apply texture to {mesh_obj.name}: {str(e)}")

    def apply_simple_texture(self, mesh_obj, texture_path, import_id):
        """Apply a single texture file to a mesh object (fallback method)"""
        try:
            print(f"Processing mesh object: {mesh_obj.name}")
            
            # Check if this is a pupil object for Selections method
            is_pupil = ("pupil-left-geo" in mesh_obj.name.lower() or 
                       "pupil-right-geo" in mesh_obj.name.lower())
            
            # Ensure we're in object mode
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Apply material based on object type
            if is_pupil:
                # Apply solid eye color for pupil objects (only for Selections method)
                props = bpy.context.scene.hytopia_props
                if props.skin_method == 'SELECT':
                    print(f"  Applying solid eye color to pupil: {mesh_obj.name}")
                    for mat in mesh_obj.data.materials:
                        pn = self._find_principled_node(mat)
                        if pn and 'Base Color' in pn.inputs:
                            pn.inputs['Base Color'].default_value = props.eye_color
                    print(f"  Applied eye color: {props.eye_color}")
                else:
                    # For other methods, apply normal texture to pupils too
                    print(f"  Applying normal texture to pupil for non-Selections method: {mesh_obj.name}")
                    # load image then set on materials
                    abs_texture_path = os.path.abspath(texture_path)
                    img = bpy.data.images.get(os.path.basename(abs_texture_path)) or bpy.data.images.load(abs_texture_path)
                    self.apply_image_to_mesh(mesh_obj, img, import_id)
            else:
                # Apply normal texture to non-pupil objects
                abs_texture_path = os.path.abspath(texture_path)
                img = bpy.data.images.get(os.path.basename(abs_texture_path)) or bpy.data.images.load(abs_texture_path)
                self.apply_image_to_mesh(mesh_obj, img, import_id)
            
        except Exception as e:
            print(f"Failed to apply texture to {mesh_obj.name}: {str(e)}")
    
    def apply_texture_to_principled(self, principled_node, texture_path, import_id):
        """Helper method to apply texture to principled BSDF node"""
        # Create and configure texture node
        if texture_path and os.path.exists(texture_path):
            print(f"  Applying texture: {os.path.basename(texture_path)}")
            
            # Create image texture node
            texture_node = principled_node.id_data.node_tree.nodes.new(type='ShaderNodeTexImage')
            texture_node.location = (-600, 300)
            texture_node.name = f"Character_Texture_{import_id}"
            
            # Load texture with unique naming
            texture_name = f"{os.path.splitext(os.path.basename(texture_path))[0]}_{import_id}"
            texture_ext = os.path.splitext(texture_path)[1]
            unique_texture_name = f"{texture_name}{texture_ext}"
            
            # Check if image already exists with unique name
            existing_image = bpy.data.images.get(unique_texture_name)
            if existing_image:
                # Use existing image
                texture_node.image = existing_image
                print(f"  Using existing image: {unique_texture_name}")
            else:
                # Load new image with unique name
                try:
                    # Use absolute path to ensure proper loading
                    abs_texture_path = os.path.abspath(texture_path)
                    texture_image = bpy.data.images.load(abs_texture_path)
                    texture_image.name = unique_texture_name
                    texture_node.image = texture_image
                    print(f"  Loaded new image: {unique_texture_name} from {abs_texture_path}")
                except Exception as e:
                    print(f"  Failed to load image: {e}")
                    return
            
            # Set interpolation to Closest for pixel-perfect textures
            texture_node.interpolation = 'Closest'
            
            # Connect to Principled BSDF
            node_tree = principled_node.id_data.node_tree
            node_tree.links.new(texture_node.outputs['Color'], principled_node.inputs['Base Color'])
            node_tree.links.new(texture_node.outputs['Alpha'], principled_node.inputs['Alpha'])
            
            print(f"  Successfully applied texture")
        else:
            print(f"  No texture to apply")
    

    
    def download_texture(self, texture_path, cache_dir):
        """Download a texture from the Hytopia repository to persistent cache"""
        try:
            url = f"{bpy.context.scene.hytopia_props.textures_url}/{texture_path}"
            local_path = os.path.join(cache_dir, os.path.basename(texture_path))
            
            # Check if already cached
            if os.path.exists(local_path):
                print(f"Using cached texture: {os.path.basename(texture_path)}")
                return local_path
            
            print(f"Downloading texture: {url}")
            urllib.request.urlretrieve(url, local_path)
            
            if os.path.exists(local_path):
                print(f"Successfully downloaded: {os.path.basename(texture_path)}")
                return local_path
            return None
            
        except Exception as e:
            print(f"Failed to download texture {texture_path}: {str(e)}")
            return None

class HYTOPIA_OT_InstallPIL(Operator):
    """Install PIL/Pillow for texture compositing"""
    bl_idname = "hytopia.install_pil"
    bl_label = "Install PIL/Pillow"
    bl_description = "Install PIL/Pillow library for advanced texture compositing"
    
    def execute(self, context):
        try:
            # First check if PIL is already available
            try:
                from PIL import Image
                self.report({'INFO'}, "PIL/Pillow is already available!")
                return {'FINISHED'}
            except ImportError:
                pass
            
            # Try installation
            if ensure_pil_installed():
                self.report({'INFO'}, "PIL/Pillow installed successfully! You may need to restart Blender.")
            else:
                self.report({'ERROR'}, "Failed to install PIL/Pillow. Check console for details.")
        except Exception as e:
            self.report({'ERROR'}, f"Installation error: {str(e)}")
        return {'FINISHED'}

class HYTOPIA_OT_ManualInstallPIL(Operator):
    """Provide manual installation instructions for PIL/Pillow"""
    bl_idname = "hytopia.manual_install_pil"
    bl_label = "Manual Install Instructions"
    bl_description = "Show manual installation instructions for PIL/Pillow"
    
    def execute(self, context):
        # Show detailed instructions
        self.report({'INFO'}, "Manual installation instructions:")
        print("\n=== Manual PIL/Pillow Installation ===")
        print("If automatic installation fails, try these steps:")
        print("\n1. Open Blender's Python Console:")
        print("   Window > Toggle System Console")
        print("\n2. Run this command:")
        print("   import subprocess, sys")
        print("   subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow'])")
        print("\n3. Restart Blender completely")
        print("\n4. Alternative command line method:")
        print("   Open Command Prompt as Administrator and run:")
        print("   \"C:\\Program Files\\Blender Foundation\\Blender 4.3\\4.3\\python\\bin\\python.exe\" -m pip install Pillow")
        print("\n5. After installation, restart Blender")
        
        return {'FINISHED'}

class HYTOPIA_OT_RefreshTextures(Operator):
    """Refresh available texture options"""
    bl_idname = "hytopia.refresh_textures"
    bl_label = "Refresh Textures"
    bl_description = "Refresh available texture options from repository"
    
    def execute(self, context):
        """Refresh texture options"""
        if update_texture_options():
            self.report({'INFO'}, "Texture options refreshed successfully")
        else:
            self.report({'WARNING'}, "Failed to refresh texture options")
        return {'FINISHED'}

class HYTOPIA_OT_SelectSkin(Operator):
    """Open skin texture selection window"""
    bl_idname = "hytopia.select_skin"
    bl_label = "Select Skin"
    bl_description = "Open skin texture selection window"
    
    def execute(self, context):
        """Open skin selection window"""
        bpy.ops.wm.call_menu(name="HYTOPIA_MT_skin_menu")
        return {'FINISHED'}

class HYTOPIA_OT_SelectClothing(Operator):
    """Open clothing texture selection window"""
    bl_idname = "hytopia.select_clothing"
    bl_label = "Select Clothing"
    bl_description = "Open clothing texture selection window"
    
    def execute(self, context):
        """Open clothing selection window"""
        bpy.ops.wm.call_menu(name="HYTOPIA_MT_clothing_menu")
        return {'FINISHED'}

class HYTOPIA_OT_SelectEyes(Operator):
    """Open eye texture selection window"""
    bl_idname = "hytopia.select_eyes"
    bl_label = "Select Eyes"
    bl_description = "Open eye texture selection window"
    
    def execute(self, context):
        """Open eye selection window"""
        bpy.ops.wm.call_menu(name="HYTOPIA_MT_eyes_menu")
        return {'FINISHED'}

class HYTOPIA_OT_SelectHairStyle(Operator):
    """Open hair style selection window"""
    bl_idname = "hytopia.select_hair_style"
    bl_label = "Select Hair Style"
    bl_description = "Open hair style selection window"
    
    def execute(self, context):
        """Open hair style selection window"""
        bpy.ops.wm.call_menu(name="HYTOPIA_MT_hair_style_menu")
        return {'FINISHED'}

class HYTOPIA_OT_SelectHairColor(Operator):
    """Open hair color selection window"""
    bl_idname = "hytopia.select_hair_color"
    bl_label = "Select Hair Color"
    bl_description = "Open hair color selection window"
    
    def execute(self, context):
        """Open hair color selection window"""
        bpy.ops.wm.call_menu(name="HYTOPIA_MT_hair_color_menu")
        return {'FINISHED'}

class HYTOPIA_OT_SelectCustomHairType(Operator):
    """Open custom hair type selection window"""
    bl_idname = "hytopia.select_custom_hair_type"
    bl_label = "Select Custom Hair Type"
    bl_description = "Open hair type selection window for custom skin method"
    
    def execute(self, context):
        """Open custom hair type selection window"""
        # Auto-refresh hair style options first
        update_texture_options()
        bpy.ops.wm.call_menu(name="HYTOPIA_MT_custom_hair_type_menu")
        return {'FINISHED'}

# Menu classes for texture selection
class HYTOPIA_MT_skin_menu(Menu):
    """Skin texture selection menu"""
    bl_idname = "HYTOPIA_MT_skin_menu"
    bl_label = "Select Skin Texture"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.hytopia_props
        
        # Get available skin options (excluding default)
        skin_options = texture_options_cache.get('skin', [])
        for item in skin_options:
            if item[0] != 'default':  # Skip default entirely
                layout.operator("hytopia.set_skin", text=item[1]).skin_type = item[0]

class HYTOPIA_MT_clothing_menu(Menu):
    """Clothing texture selection menu"""
    bl_idname = "HYTOPIA_MT_clothing_menu"
    bl_label = "Select Clothing"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.hytopia_props
        
        # Get available clothing options (excluding none)
        clothing_options = texture_options_cache.get('clothing', [])
        for item in clothing_options:
            if item[0] != 'none':  # Skip none entirely
                layout.operator("hytopia.set_clothing", text=item[1]).clothing_type = item[0]

class HYTOPIA_MT_eyes_menu(Menu):
    """Eye texture selection menu"""
    bl_idname = "HYTOPIA_MT_eyes_menu"
    bl_label = "Select Eyes"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.hytopia_props
        
        # None option
        layout.operator("hytopia.set_eyes", text="None").eye_type = "none"
        
        # Get available eye options
        eye_options = texture_options_cache.get('eyes', [])
        for item in eye_options:
            if item[0] != 'none':  # Skip none as it's already shown
                layout.operator("hytopia.set_eyes", text=item[1]).eye_type = item[0]

class HYTOPIA_MT_hair_style_menu(Menu):
    """Hair style selection menu"""
    bl_idname = "HYTOPIA_MT_hair_style_menu"
    bl_label = "Select Hair Style"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.hytopia_props
        
        # Get available hair style options
        hair_style_options = texture_options_cache.get('hair_styles', [])
        for item in hair_style_options:
            layout.operator("hytopia.set_hair_style", text=item[1]).hair_style = item[0]

class HYTOPIA_MT_hair_color_menu(Menu):
    """Hair color selection menu"""
    bl_idname = "HYTOPIA_MT_hair_color_menu"
    bl_label = "Select Hair Color"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.hytopia_props
        
        # Get available hair color options
        hair_color_options = texture_options_cache.get('hair_colors', [])
        for item in hair_color_options:
            layout.operator("hytopia.set_hair_color", text=item[1]).hair_color = item[0]

class HYTOPIA_MT_custom_hair_type_menu(Menu):
    """Custom hair type selection menu"""
    bl_idname = "HYTOPIA_MT_custom_hair_type_menu"
    bl_label = "Select Custom Hair Type"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.hytopia_props
        
        # Get available hair type options
        hair_type_options = texture_options_cache.get('hair_styles', [])
        for item in hair_type_options:
            layout.operator("hytopia.set_custom_hair_type", text=item[1]).custom_hair_type = item[0]

# Setter operators for menu selections
class HYTOPIA_OT_SetSkin(Operator):
    """Set skin texture type"""
    bl_idname = "hytopia.set_skin"
    bl_label = "Set Skin"
    
    skin_type: StringProperty()
    
    def execute(self, context):
        context.scene.hytopia_props.skin_type = self.skin_type
        return {'FINISHED'}

class HYTOPIA_OT_SetClothing(Operator):
    """Set clothing texture type"""
    bl_idname = "hytopia.set_clothing"
    bl_label = "Set Clothing"
    
    clothing_type: StringProperty()
    
    def execute(self, context):
        context.scene.hytopia_props.clothing_type = self.clothing_type
        return {'FINISHED'}

class HYTOPIA_OT_SetEyes(Operator):
    """Set eye texture type"""
    bl_idname = "hytopia.set_eyes"
    bl_label = "Set Eyes"
    
    eye_type: StringProperty()
    
    def execute(self, context):
        context.scene.hytopia_props.eye_type = self.eye_type
        return {'FINISHED'}

class HYTOPIA_OT_SetHairStyle(Operator):
    """Set hair style"""
    bl_idname = "hytopia.set_hair_style"
    bl_label = "Set Hair Style"
    
    hair_style: StringProperty()
    
    def execute(self, context):
        context.scene.hytopia_props.hair_style = self.hair_style
        
        # Update hair visibility in real-time if SELECT method is active
        props = context.scene.hytopia_props
        if props.skin_method == 'SELECT':
            # Find all Hytopia character objects in the scene
            hytopia_objects = [obj for obj in bpy.context.scene.objects 
                             if 'hytopia_character_' in obj.name]
            if hytopia_objects:
                import_op = HYTOPIA_OT_ImportPlayer()
                primary_mesh = import_op.find_primary_mesh(hytopia_objects)
                if primary_mesh:
                    import_op.apply_hair_masks_for_method(primary_mesh, props)
        
        return {'FINISHED'}

class HYTOPIA_OT_SetHairColor(Operator):
    """Set hair color"""
    bl_idname = "hytopia.set_hair_color"
    bl_label = "Set Hair Color"
    
    hair_color: StringProperty()
    
    def execute(self, context):
        context.scene.hytopia_props.hair_color = self.hair_color
        return {'FINISHED'}

class HYTOPIA_OT_SetCustomHairType(Operator):
    """Set custom hair type"""
    bl_idname = "hytopia.set_custom_hair_type"
    bl_label = "Set Custom Hair Type"
    
    custom_hair_type: StringProperty()
    
    def execute(self, context):
        context.scene.hytopia_props.custom_hair_type = self.custom_hair_type
        
        # Update hair visibility in real-time if CUSTOM method is active
        props = context.scene.hytopia_props
        if props.skin_method == 'CUSTOM':
            # Find all Hytopia character objects in the scene
            hytopia_objects = [obj for obj in bpy.context.scene.objects 
                             if 'hytopia_character_' in obj.name]
            if hytopia_objects:
                import_op = HYTOPIA_OT_ImportPlayer()
                primary_mesh = import_op.find_primary_mesh(hytopia_objects)
                if primary_mesh:
                    import_op.apply_hair_masks_for_method(primary_mesh, props)
        
        return {'FINISHED'}

class HYTOPIA_OT_UseDefaultSkin(Operator):
    """Use default skin from GLTF model"""
    bl_idname = "hytopia.use_default_skin"
    bl_label = "Default Skin"
    bl_description = "Use the default skin texture baked into the player model"
    
    def execute(self, context):
        context.scene.hytopia_props.skin_method = 'DEFAULT'
        self.report({'INFO'}, "Default skin method selected")
        return {'FINISHED'}

class HYTOPIA_OT_UseSelectSkin(Operator):
    """Use skin selection from Hytopia options"""
    bl_idname = "hytopia.use_select_skin"
    bl_label = "Select Skin Options"
    bl_description = "Choose from available Hytopia skin customization options"
    
    def execute(self, context):
        context.scene.hytopia_props.skin_method = 'SELECT'
        
        # Auto-refresh texture options
        if update_texture_options():
            # Set defaults to first available options instead of placeholders
            self.set_default_selections(context)
            self.report({'INFO'}, "Skin selection method activated with refreshed options")
        else:
            self.report({'WARNING'}, "Skin selection method activated but failed to refresh options")
        
        return {'FINISHED'}
    
    def set_default_selections(self, context):
        """Set default selections to first available options"""
        props = context.scene.hytopia_props
        
        # Set skin to first non-default option
        skin_options = texture_options_cache.get('skin', [])
        if len(skin_options) > 1:  # More than just default
            for item in skin_options:
                if item[0] != 'default':
                    props.skin_type = item[0]
                    break
        
        # Set clothing to first non-none option
        clothing_options = texture_options_cache.get('clothing', [])
        if len(clothing_options) > 1:  # More than just none
            for item in clothing_options:
                if item[0] != 'none':
                    props.clothing_type = item[0]
                    break
        
        # Eye color already has a good default (brown color picker)
        
        # Set hair style to first available option (or keep default 8)
        hair_style_options = texture_options_cache.get('hair_styles', [])
        if hair_style_options:
            # Check if style 8 is available, otherwise use first available
            style_8_available = any(item[0] == '8' for item in hair_style_options)
            if style_8_available:
                props.hair_style = '8'
            else:
                props.hair_style = hair_style_options[0][0]
        
        # Set hair color to first available option (or keep default brown)
        hair_color_options = texture_options_cache.get('hair_colors', [])
        if hair_color_options:
            # Check if brown is available, otherwise use first available
            brown_available = any(item[0] == 'brown' for item in hair_color_options)
            if brown_available:
                props.hair_color = 'brown'  # Keep default
            else:
                props.hair_color = hair_color_options[0][0]  # Use first available

class HYTOPIA_OT_UseCustomSkin(Operator):
    """Use custom skin texture file"""
    bl_idname = "hytopia.use_custom_skin"
    bl_label = "Upload Custom Skin"
    bl_description = "Use your own custom skin texture file"
    
    def execute(self, context):
        context.scene.hytopia_props.skin_method = 'CUSTOM'
        self.report({'INFO'}, "Custom skin method selected - specify your texture file path")
        return {'FINISHED'}

class HYTOPIA_PT_MainPanel(Panel):
    """Main panel for Hytopia Character Importer"""
    bl_label = "Hytopia Character Importer"
    bl_idname = "HYTOPIA_PT_character_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hytopia"
    
    def draw(self, context):
        """Draw the panel UI"""
        layout = self.layout
        props = context.scene.hytopia_props
        
        # Title
        layout.label(text="Import Hytopia Player Model", icon='ARMATURE_DATA')
        layout.separator()
        
        # Source info
        box = layout.box()
        box.label(text="Source:", icon='URL')
        col = box.column()
        col.scale_y = 0.7
        col.label(text="Appends 'Hytopia Character' from bundled .blend")
        col.label(text="Textures still fetched from hytopiagg/assets for Selections")
        
        layout.separator()
        
        # Skin method selection - 3 buttons side by side
        box = layout.box()
        box.label(text="Choose Skin Method:", icon='MATERIAL')
        
        row = box.row(align=True)
        row.scale_y = 1.2
        
        # Method 1: Default Skin
        sub1 = row.row()
        sub1.alert = (props.skin_method == 'DEFAULT')
        sub1.operator("hytopia.use_default_skin", text="Default")
        
        # Method 2: Select Skin Options  
        sub2 = row.row()
        sub2.alert = (props.skin_method == 'SELECT')
        sub2.operator("hytopia.use_select_skin", text="Selections")
        
        # Method 3: Upload Custom Skin
        sub3 = row.row()
        sub3.alert = (props.skin_method == 'CUSTOM')
        sub3.operator("hytopia.use_custom_skin", text="Custom")
        
        layout.separator()
        
        # Conditional options based on selected method
        if props.skin_method == 'DEFAULT':
            # Default method - show info
            box = layout.box()
            box.label(text="Default Skin Selected", icon='INFO')
            col = box.column()
            col.scale_y = 0.8
            col.label(text="Uses embedded material from the .blend")
            col.label(text="Hair style defaults to 8 via masks")
            
        elif props.skin_method == 'SELECT':
            # Select method - show character customization options
            box = layout.box()
            box.label(text="Character Customization:", icon='USER')
            
            # Skin selection
            row = box.row()
            row.label(text="Skin Type:", icon='MATERIAL')
            skin_display_text = "Select Skin..." 
            # Show actual selection if it's not the default/placeholder
            skin_options = texture_options_cache.get('skin', [])
            for item in skin_options:
                if item[0] == props.skin_type and item[0] != 'default':
                    skin_display_text = item[1]  # Use display name
                    break
            row.operator("hytopia.select_skin", text=skin_display_text)
            
            # Clothing selection
            row = box.row()
            row.label(text="Clothing:", icon='OUTLINER_OB_MESH')
            clothing_display_text = "Select Clothing..."
            # Show actual selection if it's not the default/placeholder
            clothing_options = texture_options_cache.get('clothing', [])
            for item in clothing_options:
                if item[0] == props.clothing_type and item[0] != 'none':
                    clothing_display_text = item[1]  # Use display name
                    break
            row.operator("hytopia.select_clothing", text=clothing_display_text)
            
            # Eye color picker (instead of eye selection)
            row = box.row()
            row.label(text="Eye Color:", icon='HIDE_OFF')
            row.prop(props, "eye_color", text="")
            
            # Hair selection
            row = box.row()
            row.label(text="Hair Style:", icon='MOD_PARTICLES')
            hair_style_display_text = "Select Hair Style..."
            # Show actual selection if it's not the default/placeholder
            hair_style_options = texture_options_cache.get('hair_styles', [])
            for item in hair_style_options:
                if item[0] == props.hair_style and item[0] != '3':  # 3 is now default
                    hair_style_display_text = item[1]  # Use display name
                    break
            # Special case: if hair_style is 3 and we have options, show it
            if props.hair_style == '3' and hair_style_options:
                for item in hair_style_options:
                    if item[0] == '3':
                        hair_style_display_text = item[1]
                        break
            row.operator("hytopia.select_hair_style", text=hair_style_display_text)
            
            row = box.row()
            row.label(text="Hair Color:", icon='COLOR')
            hair_color_display_text = "Select Hair Color..."
            # Show actual selection if it's not the default/placeholder
            hair_color_options = texture_options_cache.get('hair_colors', [])
            for item in hair_color_options:
                if item[0] == props.hair_color and item[0] != 'brown':
                    hair_color_display_text = item[1]  # Use display name
                    break
            # Special case: if hair_color is brown and we have options, show it
            if props.hair_color == 'brown' and hair_color_options:
                for item in hair_color_options:
                    if item[0] == 'brown':
                        hair_color_display_text = item[1]
                        break
            row.operator("hytopia.select_hair_color", text=hair_color_display_text)
            
        elif props.skin_method == 'CUSTOM':
            # Custom method - show file path input
            box = layout.box()
            box.label(text="Custom Skin Texture:", icon='TEXTURE')
            box.prop(props, "custom_skin_path", text="File Path")
            
            # Hair type selection for custom method
            row = box.row()
            row.label(text="Hair Type:", icon='MOD_PARTICLES')
            hair_type_display_text = f"Style {props.custom_hair_type}" if props.custom_hair_type != '3' else "Select Hair Type..."
            row.operator("hytopia.select_custom_hair_type", text=hair_type_display_text)
            
            # Show file format info
            col = box.column()
            col.scale_y = 0.8
            col.label(text="Recommended: 256 x 256 PNG")
        
        layout.separator()
        
        # PIL Status and Installation (only show if SELECT method is chosen)
        if props.skin_method == 'SELECT':
            try:
                from PIL import Image
                pil_available = True
            except ImportError:
                pil_available = False
            
            if not pil_available:
                box = layout.box()
                box.label(text="⚠️ PIL/Pillow Required", icon='ERROR')
                col = box.column()
                col.scale_y = 0.8
                col.label(text="Advanced texture compositing")
                col.label(text="requires PIL/Pillow library.")
                
                # Installation buttons
                row = col.row()
                row.operator("hytopia.install_pil", text="Auto Install", icon='PLUGIN')
                row.operator("hytopia.manual_install_pil", text="Manual Instructions", icon='HELP')
            else:
                box = layout.box()
                box.label(text="✅ PIL/Pillow Available", icon='CHECKMARK')
                col = box.column()
                col.scale_y = 0.8
                col.label(text="Advanced texture compositing")
                col.label(text="is available.")
            
            layout.separator()
            
            # Import animations option (only for SELECT method)
            layout.prop(props, "import_animations", icon='ANIM')
            layout.separator()
        else:
            # Import animations option (for other methods)
            layout.prop(props, "import_animations", icon='ANIM')
            layout.separator()
        
        # Import button
        layout.operator("hytopia.import_player", text="Import Player", icon='IMPORT')
        
# Registration
classes = [
    HytopiaProperties,
    HYTOPIA_OT_ImportPlayer,
    HYTOPIA_OT_InstallPIL,
    HYTOPIA_OT_ManualInstallPIL,
    HYTOPIA_OT_RefreshTextures,
    HYTOPIA_OT_SelectSkin,
    HYTOPIA_OT_SelectClothing,
    HYTOPIA_OT_SelectEyes,
    HYTOPIA_OT_SelectHairStyle,
    HYTOPIA_OT_SelectHairColor,
    HYTOPIA_OT_SelectCustomHairType,
    HYTOPIA_OT_SetSkin,
    HYTOPIA_OT_SetClothing,
    HYTOPIA_OT_SetEyes,
    HYTOPIA_OT_SetHairStyle,
    HYTOPIA_OT_SetHairColor,
    HYTOPIA_OT_SetCustomHairType,
    HYTOPIA_OT_UseDefaultSkin,
    HYTOPIA_OT_UseSelectSkin,
    HYTOPIA_OT_UseCustomSkin,
    HYTOPIA_MT_skin_menu,
    HYTOPIA_MT_clothing_menu,
    HYTOPIA_MT_eyes_menu,
    HYTOPIA_MT_hair_style_menu,
    HYTOPIA_MT_hair_color_menu,
    HYTOPIA_MT_custom_hair_type_menu,
    HYTOPIA_PT_MainPanel,
]

def register():
    """Register all classes and properties"""
    # Register classes
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Add properties to scene
    bpy.types.Scene.hytopia_props = bpy.props.PointerProperty(type=HytopiaProperties)
    
    print("Hytopia Character Importer registered successfully")

def unregister():
    """Unregister all classes and properties"""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Remove properties from scene
    del bpy.types.Scene.hytopia_props

if __name__ == "__main__":
    register() 