#!/usr/bin/env python3
"""
Test script for PIL/Pillow installation and texture compositing functionality
"""

import sys
import subprocess
import os

def test_pil_installation():
    """Test PIL/Pillow installation and basic functionality"""
    print("Testing PIL/Pillow installation...")
    
    # Test 1: Check if PIL is already available
    try:
        from PIL import Image
        print("✅ PIL/Pillow is already available")
        return True
    except ImportError:
        print("❌ PIL/Pillow not found, attempting installation...")
    
    # Test 2: Try to install PIL
    try:
        python_exe = sys.executable
        print(f"Using Python executable: {python_exe}")
        
        # Try to upgrade pip first
        try:
            subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pip"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✅ Pip updated successfully")
        except Exception as e:
            print(f"⚠️ Pip update failed (non-critical): {e}")
        
        # Try to install Pillow with --user flag
        try:
            subprocess.check_call([python_exe, "-m", "pip", "install", "--user", "Pillow"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✅ Pillow installed with --user flag")
        except Exception as e:
            print(f"⚠️ User installation failed, trying system install: {e}")
            # Fallback to system install
            subprocess.check_call([python_exe, "-m", "pip", "install", "Pillow"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✅ Pillow installed system-wide")
        
        # Test 3: Try importing again
        from PIL import Image
        print("✅ PIL/Pillow successfully installed and imported")
        return True
        
    except Exception as e:
        print(f"❌ Failed to install PIL/Pillow: {e}")
        return False

def test_texture_compositing():
    """Test basic texture compositing functionality"""
    try:
        from PIL import Image
        
        # Create a simple test composite
        base_size = (64, 64)
        composite = Image.new('RGBA', base_size, (0, 0, 0, 0))
        
        # Create a simple test layer (red square)
        test_layer = Image.new('RGBA', base_size, (255, 0, 0, 128))
        
        # Composite the layers
        result = Image.alpha_composite(composite, test_layer)
        
        print("✅ Texture compositing test passed")
        return True
        
    except Exception as e:
        print(f"❌ Texture compositing test failed: {e}")
        return False

def main():
    """Main test function"""
    print("=== PIL/Pillow Installation and Texture Compositing Test ===\n")
    
    # Test PIL installation
    pil_ok = test_pil_installation()
    
    if pil_ok:
        # Test texture compositing
        compositing_ok = test_texture_compositing()
        
        if compositing_ok:
            print("\n🎉 All tests passed! PIL/Pillow is working correctly.")
        else:
            print("\n⚠️ PIL installed but compositing failed.")
    else:
        print("\n❌ PIL installation failed. Check the error messages above.")
        print("\nManual installation options:")
        print("1. Open Blender's Python console and run:")
        print("   import subprocess, sys")
        print("   subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow'])")
        print("\n2. Or use command line:")
        print("   \"C:\\Program Files\\Blender Foundation\\Blender 4.3\\4.3\\python\\bin\\python.exe\" -m pip install Pillow")

if __name__ == "__main__":
    main() 