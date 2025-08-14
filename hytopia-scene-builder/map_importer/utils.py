"""
Utility functions for Hytopia world import
"""
import json
import os
from typing import Dict, List, Tuple, Optional, Any
import bpy


def parse_hytopia_coords(coord_str: str) -> Tuple[float, float, float]:
    """
    Parse Hytopia coordinate string "x,y,z" to tuple.
    
    Args:
        coord_str: String in format "x,y,z" 
        
    Returns:
        Tuple of (x, y, z) coordinates
    """
    try:
        x, y, z = map(float, coord_str.split(','))
        return (x, y, z)
    except ValueError as e:
        print(f"Error parsing coordinates '{coord_str}': {e}")
        return (0, 0, 0)


def coords_in_bounds(coords: Tuple[float, float, float], 
                    min_bounds: Tuple[float, float, float],
                    max_bounds: Tuple[float, float, float]) -> bool:
    """
    Check if coordinates are within specified bounds.
    
    Args:
        coords: (x, y, z) coordinates to check
        min_bounds: (x, y, z) minimum bounds
        max_bounds: (x, y, z) maximum bounds
        
    Returns:
        True if coordinates are within bounds
    """
    x, y, z = coords
    min_x, min_y, min_z = min_bounds
    max_x, max_y, max_z = max_bounds
    
    return (min_x <= x <= max_x and 
            min_y <= y <= max_y and 
            min_z <= z <= max_z)


def load_hytopia_map(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Load and parse Hytopia JSON map file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary containing map data, or None if failed
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            
        # Validate required sections
        if 'blockTypes' not in data:
            print("Error: Map file missing 'blockTypes' section")
            return None
        if 'blocks' not in data:
            print("Error: Map file missing 'blocks' section")
            return None
            
        print(f"Successfully loaded map with {len(data['blocks'])} blocks")
        return data
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        return None
    except Exception as e:
        print(f"Error loading map file: {e}")
        return None


def validate_bounds(min_bounds: Tuple[float, float, float],
                   max_bounds: Tuple[float, float, float]) -> bool:
    """
    Validate that bounds are reasonable and properly ordered.
    
    Args:
        min_bounds: (x, y, z) minimum bounds
        max_bounds: (x, y, z) maximum bounds
        
    Returns:
        True if bounds are valid
    """
    min_x, min_y, min_z = min_bounds
    max_x, max_y, max_z = max_bounds
    
    # Check order
    if min_x >= max_x or min_y >= max_y or min_z >= max_z:
        print("Error: Invalid bounds - minimums must be less than maximums")
        return False
        
    # Check reasonable size (prevent memory issues)
    volume = (max_x - min_x) * (max_y - min_y) * (max_z - min_z)
    if volume > 1000000:  # 100x100x100 blocks max
        print(f"Warning: Import volume ({volume}) is very large and may cause performance issues")
        
    return True


def get_block_registry(map_data: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """
    Convert blockTypes array to lookup dictionary keyed by ID.
    
    Args:
        map_data: Loaded map data dictionary
        
    Returns:
        Dictionary mapping block ID to block type data
    """
    registry = {}
    
    for block_type in map_data.get('blockTypes', []):
        if 'id' in block_type:
            registry[block_type['id']] = block_type
    
    return registry


def filter_blocks_in_bounds(map_data: Dict[str, Any],
                           min_bounds: Tuple[float, float, float],
                           max_bounds: Tuple[float, float, float]) -> Dict[Tuple[float, float, float], int]:
    """
    Extract blocks within specified bounds from map data.
    
    Args:
        map_data: Loaded map data dictionary
        min_bounds: (x, y, z) minimum bounds
        max_bounds: (x, y, z) maximum bounds
        
    Returns:
        Dictionary mapping coordinates to block type IDs
    """
    filtered_blocks = {}
    blocks_processed = 0
    blocks_in_bounds = 0
    
    for coord_str, block_id in map_data.get('blocks', {}).items():
        blocks_processed += 1
        coords = parse_hytopia_coords(coord_str)
        
        if coords_in_bounds(coords, min_bounds, max_bounds):
            filtered_blocks[coords] = block_id
            blocks_in_bounds += 1
            
        # Progress feedback for large datasets
        if blocks_processed % 10000 == 0:
            print(f"Processed {blocks_processed} blocks, {blocks_in_bounds} in bounds")
    
    print(f"Filtered {blocks_in_bounds} blocks from {blocks_processed} total")
    return filtered_blocks


def filter_entities_in_bounds(map_data: Dict[str, Any],
                             min_bounds: Tuple[float, float, float],
                             max_bounds: Tuple[float, float, float]) -> Dict[Tuple[float, float, float], Dict[str, Any]]:
    """
    Extract entities within specified bounds from map data.
    
    Args:
        map_data: Loaded map data dictionary
        min_bounds: (x, y, z) minimum bounds 
        max_bounds: (x, y, z) maximum bounds
        
    Returns:
        Dictionary mapping coordinates to entity data
    """
    filtered_entities = {}
    
    for coord_str, entity_data in map_data.get('entities', {}).items():
        coords = parse_hytopia_coords(coord_str)
        
        if coords_in_bounds(coords, min_bounds, max_bounds):
            filtered_entities[coords] = entity_data
    
    print(f"Filtered {len(filtered_entities)} entities")
    return filtered_entities


def validate_texture_path(texture_path: str, texture_base_path: str) -> str:
    """
    Validate and resolve texture file path with flexible mapping.
    
    Args:
        texture_path: Relative path from blockType (e.g., "blocks/grass.png")
        texture_base_path: Base directory for textures
        
    Returns:
        Full path to texture file, or empty string if not found
    """
    if not texture_base_path or not texture_path:
        return ""
    
    # Try different path combinations to find the texture
    potential_paths = []
    
    # Original path as specified
    potential_paths.append(os.path.join(texture_base_path, texture_path))
    
    # Just the filename (removes "blocks/" prefix)
    filename = os.path.basename(texture_path)
    potential_paths.append(os.path.join(texture_base_path, filename))
    
    # Remove first directory level (e.g., "blocks/grass.png" -> "grass.png")
    if '/' in texture_path or '\\' in texture_path:
        path_parts = texture_path.replace('\\', '/').split('/')
        if len(path_parts) > 1:
            potential_paths.append(os.path.join(texture_base_path, '/'.join(path_parts[1:])))
    
    # Try each potential path
    for i, full_path in enumerate(potential_paths):
        normalized_path = os.path.normpath(full_path)
        print(f"  [{i+1}] Trying: {normalized_path}")
        if os.path.exists(normalized_path):
            if os.path.isdir(normalized_path):
                # It's a directory; single-texture loader cannot use this
                print(f"      ⚠ Exists but is a directory, skipping: {normalized_path}")
            elif os.path.isfile(normalized_path):
                print(f"      ✓ FOUND file: {normalized_path}")
                return normalized_path
        else:
            print(f"      ✗ Not found")
        
        # Try alternative extensions for each path
        base, ext = os.path.splitext(normalized_path)
        for alt_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tga']:
            if normalized_path.endswith(alt_ext):
                continue
            alt_path = base + alt_ext
            print(f"    Alt: {alt_path}")
            if os.path.isfile(alt_path):
                print(f"      ✓ FOUND file: {alt_path}")
                return alt_path
    
    print(f"❌ Texture not found after trying {len(potential_paths)} locations:")
    for path in potential_paths:
        print(f"   - {path}")
    return ""


def safe_name(name: str) -> str:
    """
    Convert name to Blender-safe object/material name.
    
    Args:
        name: Original name
        
    Returns:
        Name safe for use as Blender object/material name
    """
    # Replace problematic characters
    safe = name.replace(' ', '_').replace('-', '_').replace('/', '_')
    
    # Ensure it starts with a letter or underscore
    if not safe or not (safe[0].isalpha() or safe[0] == '_'):
        safe = 'hytopia_' + safe
        
    return safe


def report_progress(current: int, total: int, operation: str = "Processing"):
    """
    Report progress to Blender's info area.
    
    Args:
        current: Current progress count
        total: Total count
        operation: Description of operation
    """
    if total > 0:
        percentage = (current / total) * 100
        print(f"{operation}: {current}/{total} ({percentage:.1f}%)")
        
        # Update Blender's interface (if in Blender context)
        try:
            bpy.context.window_manager.progress_update(current)
            if hasattr(bpy.context.area, 'tag_redraw'):
                bpy.context.area.tag_redraw()
        except:
            pass  # Not in Blender context or UI not available 