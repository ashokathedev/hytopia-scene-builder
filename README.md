# Hytopia Scene Builder

A comprehensive tool for building and managing scenes for the Hytopia platform. This project includes utilities for character and world building, with support for Blender integration.

## Features

- **Scene Builder**: Create and manage 3D scenes for Hytopia games
- **Character Tools**: Import and export character models to/from Blender
- **World Builder**: Convert and manage world data for Blender
- **Texture Management**: Handle various texture formats and materials
- **Model Support**: Support for GLTF, OBJ, and other 3D model formats

## Project Structure

```
hytopia-scene-builder/
├── hytopia-character-to-blender/    # Character import/export tools
├── hytopia-world-to-blender/        # World building utilities
└── hytopia-scene-builder/          # Main scene builder application
```

## Getting Started

### Prerequisites

- Node.js (for web-based tools)
- Python 3.x (for Blender addons)
- Blender (for 3D model work)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/ashokathedev/hytopia-scene-builder.git
cd hytopia-scene-builder
```

2. Install dependencies for the web tools:
```bash
cd hytopia-scene-builder/world-editor-main
npm install
```

3. For Blender addons, install the Python dependencies:
```bash
cd hytopia-world-to-blender
pip install -r requirements.txt
```

## Usage

### Web-based Scene Builder

Navigate to the `world-editor-main` directory and run:
```bash
npm start
```

### Blender Addons

1. Install the Blender addons from the respective directories
2. Enable them in Blender's preferences
3. Use the tools to import/export Hytopia assets

## Development

This project is built with:
- TypeScript/React for the web interface
- Python for Blender addons
- Three.js for 3D rendering

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions, please open an issue on GitHub. 