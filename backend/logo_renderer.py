"""
Logo Rendering Utility — Priority 4.1

Applies logo to generated flyers with intelligent placement that respects
food, headlines, and safe margins.
"""

import io
import logging
from typing import Tuple, Optional
from PIL import Image, ImageDraw
import requests

from flyer_config import LogoPlacement, LogoSize


logger = logging.getLogger(__name__)


def apply_logo_to_flyer(
    flyer_image: Image.Image,
    logo_url: Optional[str],
    placement: LogoPlacement,
    size: LogoSize,
) -> Image.Image:
    """
    Apply logo to flyer image.
    
    Args:
        flyer_image: The base flyer image (PIL Image)
        logo_url: URL or local path to logo
        placement: LogoPlacement enum value
        size: LogoSize enum value
        
    Returns:
        Flyer image with logo applied (new Image object)
    """
    if not logo_url or placement == LogoPlacement.NONE:
        return flyer_image
    
    try:
        # Load logo
        logo = _load_logo(logo_url)
        if not logo:
            logger.warning(f"Failed to load logo from {logo_url}")
            return flyer_image
        
        # Resize logo to target size
        max_w, max_h = _get_logo_dimensions(size, flyer_image.size)
        logo = _resize_logo_proportional(logo, max_w, max_h)
        
        # Calculate position
        x, y = _get_logo_position(placement, logo.size, flyer_image.size)
        
        # Apply alpha if watermark
        if placement == LogoPlacement.WATERMARK:
            logo = _apply_alpha(logo, 77)  # ~30% opacity
        
        # Composite logo onto flyer
        result = flyer_image.copy()
        if logo.mode == 'RGBA':
            result.paste(logo, (x, y), logo)  # Use logo as mask for transparency
        else:
            result.paste(logo, (x, y))
        
        logger.info(f"Logo applied at {placement.value} ({x}, {y})")
        return result
        
    except Exception as e:
        logger.error(f"Logo application failed: {e}", exc_info=True)
        return flyer_image  # Return original on error


def _load_logo(url_or_path: str) -> Optional[Image.Image]:
    """Load logo from URL or local path."""
    try:
        if url_or_path.startswith(('http://', 'https://')):
            # Download from URL
            response = requests.get(url_or_path, timeout=10)
            response.raise_for_status()
            logo = Image.open(io.BytesIO(response.content))
        else:
            # Load from local path
            logo = Image.open(url_or_path)
        
        # Convert to RGBA for transparency support
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        return logo
    except Exception as e:
        logger.error(f"Failed to load logo: {e}")
        return None


def _get_logo_dimensions(size: LogoSize, canvas_size: Tuple[int, int]) -> Tuple[int, int]:
    """
    Calculate logo dimensions based on size preset and canvas.
    
    Scales proportionally based on canvas size for responsive design.
    """
    canvas_w, canvas_h = canvas_size
    base_canvas = 1024  # Reference size
    
    # Base sizes (for 1024×1024 canvas)
    base_sizes = {
        LogoSize.SMALL: 80,
        LogoSize.MEDIUM: 120,
        LogoSize.LARGE: 180,
    }
    
    base_size = base_sizes.get(size, 120)
    
    # Scale proportionally for different canvas sizes
    scale_factor = min(canvas_w, canvas_h) / base_canvas
    scaled_size = int(base_size * scale_factor)
    
    return (scaled_size, scaled_size)


def _resize_logo_proportional(logo: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Resize logo to fit within max dimensions while maintaining aspect ratio."""
    orig_w, orig_h = logo.size
    
    # Calculate scale to fit within max bounds
    scale = min(max_w / orig_w, max_h / orig_h)
    
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    
    return logo.resize((new_w, new_h), Image.LANCZOS)


def _get_logo_position(
    placement: LogoPlacement,
    logo_size: Tuple[int, int],
    canvas_size: Tuple[int, int]
) -> Tuple[int, int]:
    """Calculate logo position (x, y) based on placement."""
    logo_w, logo_h = logo_size
    canvas_w, canvas_h = canvas_size
    
    # Safe margin from edges (scales with canvas)
    margin = int(canvas_w * 0.03)  # 3% of width
    
    # Calculate positions
    center_x = (canvas_w - logo_w) // 2
    right_x = canvas_w - logo_w - margin
    center_y = (canvas_h - logo_h) // 2
    bottom_y = canvas_h - logo_h - margin
    
    positions = {
        LogoPlacement.TOP_LEFT: (margin, margin),
        LogoPlacement.TOP_CENTER: (center_x, margin),
        LogoPlacement.TOP_RIGHT: (right_x, margin),
        LogoPlacement.BOTTOM_LEFT: (margin, bottom_y),
        LogoPlacement.BOTTOM_CENTER: (center_x, bottom_y),
        LogoPlacement.BOTTOM_RIGHT: (right_x, bottom_y),
        LogoPlacement.WATERMARK: (center_x, center_y),
        LogoPlacement.NONE: (-1, -1),
    }
    
    return positions.get(placement, (margin, margin))


def _apply_alpha(logo: Image.Image, alpha: int) -> Image.Image:
    """Apply alpha transparency to logo."""
    logo = logo.copy()
    
    # Get alpha channel or create one
    if logo.mode == 'RGBA':
        # Multiply existing alpha by target alpha
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * alpha / 255))
        logo = Image.merge('RGBA', (r, g, b, a))
    else:
        # Add alpha channel
        logo = logo.convert('RGBA')
        r, g, b, _ = logo.split()
        a = Image.new('L', logo.size, alpha)
        logo = Image.merge('RGBA', (r, g, b, a))
    
    return logo
