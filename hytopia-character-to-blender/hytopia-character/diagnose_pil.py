#!/usr/bin/env python3
"""
Diagnostic script for PIL/Pillow installation issues in Blender
"""

import sys
import os
import subprocess
import site

def diagnose_pil_installation():
    """Diagnose PIL/Pillow installation issues"""
    print("=== PIL/Pillow Installation Diagnostic ===\n")
    
    # Check Python environment
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Python prefix: {sys.prefix}")
    print(f"Python path:")
    for i, path in enumerate(sys.path):
        print(f"  {i}: {path}")
    
    print(f"\nUser site packages: {site.getusersitepackages()}")
    print(f"Site packages: {site.getsitepackages()}")
    
    # Check if PIL is already installed
    print("\n=== PIL/Pillow Status ===")
    try:
        from PIL import Image
        print("✅ PIL/Pillow is available!")
        print(f"PIL version: {Image.__version__}")
        print(f"PIL path: {Image.__file__}")
        return True
    except ImportError as e:
        print(f"❌ PIL/Pillow not found: {e}")
    
    # Check for Pillow installation
    print("\n=== Checking for Pillow installation ===")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list"], 
                              capture_output=True, text=True)
        if "Pillow" in result.stdout:
            print("✅ Pillow is installed via pip")
            print(result.stdout)
        else:
            print("❌ Pillow not found in pip list")
    except Exception as e:
        print(f"❌ Error checking pip list: {e}")
    
    # Check common installation locations
    print("\n=== Checking common installation locations ===")
    possible_paths = [
        os.path.join(site.getusersitepackages(), "PIL"),
        os.path.join(site.getusersitepackages(), "Pillow"),
        os.path.join(sys.prefix, "Lib", "site-packages", "PIL"),
        os.path.join(sys.prefix, "Lib", "site-packages", "Pillow"),
        os.path.join(sys.prefix, "Lib", "site-packages", "PIL"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Found PIL at: {path}")
        else:
            print(f"❌ Not found: {path}")
    
    # Try to install Pillow
    print("\n=== Attempting Pillow installation ===")
    try:
        # Try user installation first
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "Pillow"],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Pillow installed with --user flag")
            print("Installation output:")
            print(result.stdout)
        else:
            print("❌ User installation failed")
            print("Error output:")
            print(result.stderr)
            
            # Try system installation
            print("\nTrying system installation...")
            result = subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Pillow installed system-wide")
                print("Installation output:")
                print(result.stdout)
            else:
                print("❌ System installation failed")
                print("Error output:")
                print(result.stderr)
                
    except Exception as e:
        print(f"❌ Installation error: {e}")
    
    # Try importing after installation
    print("\n=== Testing import after installation ===")
    try:
        # Force reload of site packages
        import site
        site.main()
        
        # Add user site packages to path
        user_site = site.getusersitepackages()
        if user_site not in sys.path:
            sys.path.insert(0, user_site)
            print(f"Added user site packages: {user_site}")
        
        # Try importing
        from PIL import Image
        print("✅ PIL/Pillow successfully imported after installation!")
        return True
    except ImportError as e:
        print(f"❌ Still cannot import PIL: {e}")
        print("\n=== Manual Installation Instructions ===")
        print("1. Open Blender's Python Console (Window > Toggle System Console)")
        print("2. Run: import subprocess, sys")
        print("3. Run: subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow'])")
        print("4. Restart Blender completely")
        print("\nAlternative command line method:")
        print("1. Open Command Prompt as Administrator")
        print("2. Run: \"C:\\Program Files\\Blender Foundation\\Blender 4.3\\4.3\\python\\bin\\python.exe\" -m pip install Pillow")
        print("3. Restart Blender")
    
    return False

if __name__ == "__main__":
    diagnose_pil_installation() 