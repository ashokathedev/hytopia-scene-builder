# Hytopia Scene Builder Add-on

A comprehensive Blender add-on for building complete Hytopia scenes with three integrated components:

## 🎯 Components Overview

### 1. Map Importer ✅ (Currently Available)
- Import Hytopia world maps with blocks, textures, and entities
- Full texture and material support
- Optimized mesh generation with face culling
- Configurable import bounds for performance
- Entity placement and management

### 2. Character Importer 🚧 (Coming Soon)
- Import and manage Hytopia character models
- Character animation support
- Rigging and bone structure preservation
- Multiple character format support

### 3. Asset Importer 🚧 (Coming Soon)
- Import various Hytopia assets and models
- Support for custom 3D models
- Texture and material management
- Asset library organization

## 📁 Project Structure

```
hytopia_scene_builder/
├── __init__.py                    # Main add-on entry point
├── ui_panel.py                    # Unified UI panel for all components
├── map_importer/                  # Map importing functionality
│   ├── __init__.py
│   ├── hytopia_importer.py        # Core map import logic
│   ├── mesh_generator.py          # Mesh generation and optimization
│   ├── material_manager.py        # Material and texture handling
│   └── utils.py                   # Utility functions
├── character_importer/            # Character importing (future)
│   └── __init__.py                # Placeholder for character import
└── asset_importer/                # Asset importing (future)
    └── __init__.py                # Placeholder for asset import
```

## 🚀 Installation

1. Copy the `hytopia_scene_builder` folder to your Blender add-ons directory:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\{version}\scripts\addons\`
   - **macOS**: `~/Library/Application Support/Blender/{version}/scripts/addons/`
   - **Linux**: `~/.config/blender/{version}/scripts/addons/`

2. Open Blender and go to `Edit > Preferences > Add-ons`

3. Search for "Hytopia Scene Builder" and enable it

4. The panel will appear in the 3D Viewport sidebar under the "Hytopia" tab

## 🎮 Usage

### Map Importer (Available Now)

1. **Open the Hytopia Panel**: Look for the "Hytopia" tab in the 3D Viewport sidebar
2. **Set Texture Path**: Point to your directory containing block textures
3. **Set Model Path**: Point to your directory containing entity models  
4. **Configure Bounds**: Set import boundaries for performance optimization
5. **Import World**: Click "Import World Map" and select your Hytopia world JSON file

#### Import Settings:
- **Texture Directory**: Custom block textures location
- **Model Directory**: Entity models location  
- **Bounds Size**: Controls import area (smaller = better performance)
- **Import Blocks**: Toggle block import on/off
- **Import Entities**: Toggle entity import on/off
- **Face Culling**: Remove hidden faces for optimization

### Character & Asset Importers (Coming Soon)
These components will be added in future updates with similar easy-to-use interfaces.

## 🛠️ Development

### Current Status
- ✅ **Map Importer**: Fully functional with all features from the original add-on
- 🚧 **Character Importer**: Framework ready, implementation pending
- 🚧 **Asset Importer**: Framework ready, implementation pending

### Technical Details
- **Blender Version**: 3.0+
- **Python**: Uses Blender's built-in Python
- **Architecture**: Modular design with separate components
- **Performance**: Optimized for large world imports with configurable bounds

### Code Organization
- Each component is self-contained in its own module
- Shared utilities and UI in the root directory
- Clean import structure with proper error handling
- Extensible design for future enhancements

## 📝 Notes

This add-on incorporates the complete functionality of the original Hytopia World Importer and extends it into a comprehensive scene building toolkit. The map importer component maintains 100% compatibility with existing workflows while providing a foundation for future character and asset import capabilities.

## 🤝 Contributing

This is part of the larger Hytopia development toolkit. Future updates will add the character and asset import functionality to complete the scene building workflow.

---

**Version**: 1.0.0  
**Author**: Hytopia Team  
**Category**: Import-Export 