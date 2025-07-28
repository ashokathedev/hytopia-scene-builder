# Hytopia Character Importer for Blender

A Blender add-on that allows you to easily import Hytopia player characters directly from the official Hytopia assets repository, with a comprehensive texture layering system for character customization.

## Features

🎮 **Direct Repository Import**: Download and import player models directly from the [official Hytopia assets repository](https://github.com/hytopiagg/assets)

🎨 **Texture Layering System**: Build custom characters by layering different texture components:
- **Skin**: Multiple skin tone options
- **Clothing**: Various clothing styles (casual, formal, armor)
- **Eyes**: Different eye styles (normal, glowing, dark)
- **Hair**: 10 different hair styles with multiple color options

🕺 **Animation Import**: Automatically imports all animations and rigging from the GLTF model

🔧 **Easy-to-Use Interface**: Simple panel interface in the 3D Viewport sidebar with dropdown selections

## Installation

### Method 1: Manual Installation (Recommended)

1. **Download the add-on**:
   - Download the `__init__.py` file from this repository
   - Or clone/download the entire repository

2. **Install in Blender**:
   - Open Blender (version 3.0 or higher)
   - Go to `Edit > Preferences > Add-ons`
   - Click `Install...` and select the `__init__.py` file
   - Enable the add-on by checking the box next to "Import-Export: Hytopia Character Importer"

### Method 2: Development Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/hytopia-character-to-blender.git
   ```

2. **Link to Blender add-ons folder**:
   - Copy the entire folder to your Blender add-ons directory:
     - **Windows**: `%APPDATA%\Blender Foundation\Blender\[version]\scripts\addons\`
     - **macOS**: `~/Library/Application Support/Blender/[version]/scripts/addons/`
     - **Linux**: `~/.config/blender/[version]/scripts/addons/`

3. **Enable the add-on** in Blender Preferences as described above

## Usage

### Basic Import

1. **Open the Hytopia Panel**:
   - In the 3D Viewport, press `N` to open the sidebar
   - Look for the "Hytopia" tab
   - Click on "Hytopia Character Importer"

2. **Check PIL/Pillow Status**:
   - The panel will show if PIL/Pillow is available for advanced texture compositing
   - If not available, click "Install PIL/Pillow" to install it automatically

3. **Customize Your Character**:
   - **Skin Type**: Choose from Default, Light, Medium, or Dark skin tones
   - **Clothing**: Select from None, Casual, Formal, or Armor styles
   - **Eyes**: Choose from None, Normal, Glowing, or Dark eyes
   - **Hair Style**: Select from 1-10 different hair styles
   - **Hair Color**: Choose from 8 different hair colors

4. **Import the Player Model**:
   - Click the "Import Player" button
   - The add-on will download the model and all selected textures
   - Textures will be automatically layered in the correct order
   - Your customized character will appear in the scene!

### Texture Layering System

The add-on uses a sophisticated layering system that builds your character texture in this order:

1. **Default Skin** (base layer)
2. **Skin Overlay** (if a different skin tone is selected)
3. **Clothing Layer** (applied on top of skin)
4. **Eye Overlay** (applied on top of clothing)
5. **Hair Style & Color** (final layer)

This ensures realistic layering where hair appears on top of clothing, and clothing appears on top of skin.

### Hair System

The hair system works with the [Hytopia texture structure](https://github.com/hytopiagg/assets/tree/main/release/models/players/Textures):

- **Hair Styles**: Currently supports styles 1-10 (expandable)
- **Hair Colors**: Black, Brown, Blonde, Red, White, Blue, Green, Purple
- **File Structure**: `hairstyle-texture/[style_number]/[color].png`

### Animation Controls

- **Import Animations**: Check this option (enabled by default) to import all animations from the GLTF file
- Animations can be viewed and edited in Blender's Animation workspace

## Troubleshooting

### PIL/Pillow Installation Issues

**Problem**: "Failed to install PIL/Pillow" or "Cannot composite textures without PIL"

**Solutions**:

1. **Automatic Installation** (Recommended):
   - In the Hytopia panel, click "Install PIL/Pillow" button
   - The add-on will attempt to install PIL/Pillow automatically

2. **Manual Installation via Blender Console**:
   - Open Blender's Python console: `Window > Toggle System Console`
   - Run this command:
     ```python
     import subprocess, sys
     subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow'])
     ```

3. **Manual Installation via Command Line**:
   - Find your Blender Python executable (usually in Blender installation directory)
   - Open command prompt/terminal and run:
     ```bash
     "C:\Program Files\Blender Foundation\Blender 4.3\4.3\python\bin\python.exe" -m pip install Pillow
     ```

4. **Alternative: Use Individual Textures**:
   - If PIL installation fails, the add-on will fall back to applying individual textures
   - This still works but without advanced compositing

### Import Issues

**Problem**: "Failed to download player model"

**Solutions**:
- Check your internet connection
- Verify the model URL is accessible: https://raw.githubusercontent.com/hytopiagg/assets/main/release/models/players/player.gltf
- Try refreshing texture options using the "Refresh" button

**Problem**: "No mesh objects found"

**Solutions**:
- Make sure you have an active object selected
- Try importing again after the model loads
- Check that the GLTF file imported correctly

### Texture Issues

**Problem**: "Failed to create composite texture"

**Solutions**:
- Install PIL/Pillow using the methods above
- Check that texture files are accessible
- Try refreshing texture options

**Problem**: Textures not appearing on model

**Solutions**:
- Check that materials are assigned to mesh objects
- Verify texture files downloaded correctly
- Try the "Refresh" button to update texture options

### General Issues

**Problem**: Add-on not appearing in Blender

**Solutions**:
- Make sure you enabled the add-on in Preferences
- Restart Blender after installation
- Check that you're using Blender 3.0 or higher

**Problem**: Panel not visible

**Solutions**:
- Press `N` to open the sidebar
- Look for the "Hytopia" tab in the sidebar
- Make sure you're in the 3D Viewport

## Technical Details

### Model Source
- **Repository**: [github.com/hytopiagg/assets](https://github.com/hytopiagg/assets)
- **Direct URL**: `https://raw.githubusercontent.com/hytopiagg/assets/main/release/models/players/player.gltf`
- **Textures URL**: `https://raw.githubusercontent.com/hytopiagg/assets/main/release/models/players/Textures`

### Dependencies
- **PIL/Pillow**: Required for advanced texture compositing (auto-installed)
- **Blender 3.0+**: Required for add-on compatibility
- **Internet Connection**: Required for downloading models and textures

### Fallback System
If PIL/Pillow is not available, the add-on will:
1. Apply individual textures without compositing
2. Show a warning message
3. Still function for basic character customization

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

If you encounter any issues:
1. Check the troubleshooting section above
2. Look at the Blender Console for error messages
3. Open an issue on the GitHub repository
4. Check the [Hytopia assets repository](https://github.com/hytopiagg/assets) for updates

Happy creating! 🎮✨ 