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
from bpy.props import StringProperty, BoolProperty, IntProperty, EnumProperty
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
        
        # Layer order: Skin → Eye Base → Eye Color → Clothing → Hair
        layer_order = ['skin', 'eye_base', 'eye_color', 'clothing', 'hair']
        
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
HAIR_STYLE_FALLBACK_ITEMS = [('1', 'Style 1', 'Hair style 1')]
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
        if validated_items and not any(item[0] == '1' for item in validated_items):
            validated_items.insert(0, ('1', 'Style 1', 'Hair style 1'))
        
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
        name="Import Animations",
        description="Import animations from the GLTF file",
        default=True
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
        default="1"
    )
    
    hair_color: StringProperty(
        name="Hair Color",
        description="Selected hair color",
        default="brown"
    )

class HYTOPIA_OT_ImportPlayer(Operator):
    """Import Hytopia Player Character with Custom Textures"""
    bl_idname = "hytopia.import_player"
    bl_label = "Import Hytopia Player"
    bl_description = "Download and import the Hytopia player model with custom texture layering"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        """Execute the import operation"""
        props = context.scene.hytopia_props
        
        try:
            # Create unique directory for this import instance
            import_id = f"hytopia_character_{len(bpy.data.objects):04d}"
            addon_dir = os.path.dirname(__file__)
            cache_dir = os.path.join(addon_dir, "texture_cache", import_id)
            os.makedirs(cache_dir, exist_ok=True)
            
            temp_gltf_path = os.path.join(cache_dir, "player.gltf")
            
            # Download the GLTF file
            self.report({'INFO'}, f"Downloading player model from: {props.player_url}")
            urllib.request.urlretrieve(props.player_url, temp_gltf_path)
            
            # Check if file was downloaded successfully
            if not os.path.exists(temp_gltf_path):
                self.report({'ERROR'}, "Failed to download player model")
                return {'CANCELLED'}
            
            # Store existing objects before import
            existing_objects = set(bpy.context.scene.objects)
            
            # Import the GLTF file
            bpy.ops.import_scene.gltf(
                filepath=temp_gltf_path,
                import_pack_images=True,
                import_shading='NORMALS',
                bone_heuristic='TEMPERANCE',
                guess_original_bind_pose=True
            )
            
            # Get newly imported objects
            new_objects = set(bpy.context.scene.objects) - existing_objects
            imported_objects = list(new_objects)
            
            print(f"Imported {len(imported_objects)} new objects:")
            for obj in imported_objects:
                print(f"  - {obj.name} (type: {obj.type})")
            
            # Rename imported objects to be unique for this character
            self.rename_imported_objects(imported_objects, import_id)
            
            # Apply layered textures with unique instance ID
            self.apply_layered_textures(props, cache_dir, import_id, imported_objects)
            
            self.report({'INFO'}, f"Hytopia player model imported successfully! (ID: {import_id})")
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            return {'CANCELLED'}
    
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
            
            # Download eye base texture (always applied)
            print(f"  Downloading eye base texture")
            textures['eye_base'] = self.download_texture("eye-texture/eye-texture.png", cache_dir)
            
            # Download eye color texture
            if props.eye_type != 'none':
                print(f"  Downloading eye color texture: {props.eye_type}")
                textures['eye_color'] = self.download_texture(f"eye-texture/{props.eye_type}.png", cache_dir)
            else:
                print(f"  Skipping eye color (none selected)")
            
            # Download hair texture
            if props.hair_style != '1' or props.hair_color != 'brown':
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
        """Apply a pre-loaded composite image to a mesh object with unique material"""
        try:
            print(f"Processing mesh object: {mesh_obj.name}")
            
            # Ensure we're in object mode
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Create unique material for this instance (always create new)
            material_name = f"Hytopia_Material_{import_id}_{mesh_obj.name}_{len(bpy.data.materials):04d}"
            
            # Always create a new material to avoid conflicts
            material = bpy.data.materials.new(name=material_name)
            print(f"  Created new material: {material_name}")
            
            # Assign material to mesh object
            if mesh_obj.data.materials:
                mesh_obj.data.materials[0] = material
                print(f"  Replaced existing material slot")
            else:
                mesh_obj.data.materials.append(material)
                print(f"  Added material to empty slot")
            
            print(f"  Material assigned: {material.name}")
            
            # Ensure material uses nodes
            if not material.use_nodes:
                material.use_nodes = True
            
            # Clear existing texture nodes
            nodes_to_remove = []
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    nodes_to_remove.append(node)
            for node in nodes_to_remove:
                material.node_tree.nodes.remove(node)
            
            # Find the Principled BSDF node
            principled_node = None
            for node in material.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled_node = node
                    break
            
            if not principled_node:
                print(f"  No Principled BSDF found for {mesh_obj.name}")
                return
            
            # Create and configure texture node with the pre-loaded image
            if composite_image:
                print(f"  Applying composite image: {composite_image.name}")
                
                # Create image texture node
                texture_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
                texture_node.location = (-600, 300)
                texture_node.name = f"Character_Composite_{import_id}"
                
                # Assign the pre-loaded composite image
                texture_node.image = composite_image
                
                # Set interpolation to Closest for pixel-perfect textures
                texture_node.interpolation = 'Closest'
                
                # Connect to Principled BSDF
                material.node_tree.links.new(texture_node.outputs['Color'], principled_node.inputs['Base Color'])
                material.node_tree.links.new(texture_node.outputs['Alpha'], principled_node.inputs['Alpha'])
                
                print(f"  Successfully applied composite texture to {mesh_obj.name}")
            else:
                print(f"  No composite image provided for {mesh_obj.name}")
            
        except Exception as e:
            print(f"Failed to apply texture to {mesh_obj.name}: {str(e)}")

    def apply_simple_texture(self, mesh_obj, texture_path, import_id):
        """Apply a single texture file to a mesh object (fallback method)"""
        try:
            print(f"Processing mesh object: {mesh_obj.name}")
            
            # Ensure we're in object mode
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Create unique material for this instance (always create new)
            material_name = f"Hytopia_Material_{import_id}_{mesh_obj.name}_{len(bpy.data.materials):04d}"
            
            # Always create a new material to avoid conflicts
            material = bpy.data.materials.new(name=material_name)
            print(f"  Created new material: {material_name}")
            
            # Assign material to mesh object
            if mesh_obj.data.materials:
                mesh_obj.data.materials[0] = material
                print(f"  Replaced existing material slot")
            else:
                mesh_obj.data.materials.append(material)
                print(f"  Added material to empty slot")
            
            print(f"  Material assigned: {material.name}")
            
            # Ensure material uses nodes
            if not material.use_nodes:
                material.use_nodes = True
            
            # Clear existing texture nodes
            nodes_to_remove = []
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    nodes_to_remove.append(node)
            for node in nodes_to_remove:
                material.node_tree.nodes.remove(node)
            
            # Find the Principled BSDF node
            principled_node = None
            for node in material.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled_node = node
                    break
            
            if not principled_node:
                print(f"  No Principled BSDF found for {mesh_obj.name}")
                return
            
            # Create and configure texture node
            if texture_path and os.path.exists(texture_path):
                print(f"  Applying texture: {os.path.basename(texture_path)}")
                
                # Create image texture node
                texture_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
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
                material.node_tree.links.new(texture_node.outputs['Color'], principled_node.inputs['Base Color'])
                material.node_tree.links.new(texture_node.outputs['Alpha'], principled_node.inputs['Alpha'])
                
                print(f"  Successfully applied texture to {mesh_obj.name}")
            else:
                print(f"  No texture to apply for {mesh_obj.name}")
            
        except Exception as e:
            print(f"Failed to apply texture to {mesh_obj.name}: {str(e)}")
    

    
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

# Menu classes for texture selection
class HYTOPIA_MT_skin_menu(Menu):
    """Skin texture selection menu"""
    bl_idname = "HYTOPIA_MT_skin_menu"
    bl_label = "Select Skin Texture"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.hytopia_props
        
        # Default option
        layout.operator("hytopia.set_skin", text="Default").skin_type = "default"
        
        # Get available skin options
        skin_options = texture_options_cache.get('skin', [])
        for item in skin_options:
            if item[0] != 'default':  # Skip default as it's already shown
                layout.operator("hytopia.set_skin", text=item[1]).skin_type = item[0]

class HYTOPIA_MT_clothing_menu(Menu):
    """Clothing texture selection menu"""
    bl_idname = "HYTOPIA_MT_clothing_menu"
    bl_label = "Select Clothing"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.hytopia_props
        
        # None option
        layout.operator("hytopia.set_clothing", text="None").clothing_type = "none"
        
        # Get available clothing options
        clothing_options = texture_options_cache.get('clothing', [])
        for item in clothing_options:
            if item[0] != 'none':  # Skip none as it's already shown
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
        return {'FINISHED'}

class HYTOPIA_OT_SetHairColor(Operator):
    """Set hair color"""
    bl_idname = "hytopia.set_hair_color"
    bl_label = "Set Hair Color"
    
    hair_color: StringProperty()
    
    def execute(self, context):
        context.scene.hytopia_props.hair_color = self.hair_color
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
        
        # Model source info
        box = layout.box()
        box.label(text="Model Source:", icon='URL')
        col = box.column()
        col.scale_y = 0.7
        col.label(text="Official Hytopia Repository")
        col.label(text="github.com/hytopiagg/assets")
        
        layout.separator()
        
        # Character customization section
        box = layout.box()
        box.label(text="Character Customization:", icon='USER')
        
        # Skin selection
        row = box.row()
        row.label(text="Skin Type:", icon='MATERIAL')
        row.operator("hytopia.select_skin", text=props.skin_type.title())
        
        # Clothing selection
        row = box.row()
        row.label(text="Clothing:", icon='OUTLINER_OB_MESH')
        row.operator("hytopia.select_clothing", text=props.clothing_type.title())
        
        # Eye selection
        row = box.row()
        row.label(text="Eyes:", icon='HIDE_OFF')
        row.operator("hytopia.select_eyes", text=props.eye_type.title())
        
        # Hair selection
        row = box.row()
        row.label(text="Hair Style:", icon='MOD_PARTICLES')
        row.operator("hytopia.select_hair_style", text=f"Style {props.hair_style}")
        
        row = box.row()
        row.label(text="Hair Color:", icon='COLOR')
        row.operator("hytopia.select_hair_color", text=props.hair_color.title())
        
        layout.separator()
        
        # Options
        layout.prop(props, "import_animations", icon='ANIM')
        
        layout.separator()
        
        # PIL Status and Installation
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
        
        # Action buttons
        row = layout.row(align=True)
        row.operator("hytopia.refresh_textures", text="Refresh", icon='FILE_REFRESH')
        row.operator("hytopia.import_player", text="Import Player", icon='IMPORT')
        
        layout.separator()
        
        # Info section
        box = layout.box()
        box.label(text="Texture Layering:", icon='INFO')
        col = box.column()
        col.scale_y = 0.8
        col.label(text="1. Skin (base)")
        col.label(text="2. Eye base texture")
        col.label(text="3. Eye color (if selected)")
        col.label(text="4. Clothing layer")
        col.label(text="5. Hair style & color")

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
    HYTOPIA_OT_SetSkin,
    HYTOPIA_OT_SetClothing,
    HYTOPIA_OT_SetEyes,
    HYTOPIA_OT_SetHairStyle,
    HYTOPIA_OT_SetHairColor,
    HYTOPIA_MT_skin_menu,
    HYTOPIA_MT_clothing_menu,
    HYTOPIA_MT_eyes_menu,
    HYTOPIA_MT_hair_style_menu,
    HYTOPIA_MT_hair_color_menu,
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