# Backup of character_importer/__init__.py before switching to .blend append approach
# Timestamp and provenance are managed by git history; this file preserves the prior GLTF-based importer logic.

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

# The rest of this file is an exact copy of the GLTF-based importer implementation from
# character_importer/__init__.py at the time of backup.

# To avoid duplication errors in registration when this backup exists alongside the active addon,
# we do not re-register classes here. This file is for archival/reference only.