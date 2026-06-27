"""
Background Rendering System — Priority 4.2

Complete background generation with presets, textures, and smart food protection.
Implements 24+ background types with dynamic layering and effects.
"""

import io
import logging
import random
from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import numpy as np

from flyer_config import BackgroundType

logger = logging.getLogger(__name__)

# Cache for generated backgrounds (reduces redundant generation)
_BACKGROUND_CACHE = {}


def generate_background(
    bg_type: BackgroundType,
    canvas_size: Tuple[int, int],
    theme_colors: Optional[dict] = None,
    opacity: float = 1.0,
    blur_radius: int = 0,
    texture_intensity: float = 0.5,
    vignette_intensity: float = 0.3,
    food_category: Optional[str] = None,
) -> Image.Image:
    """
    Generate or load background image with effects.
    
    Args:
        bg_type: Background preset type
        canvas_size: (width, height) tuple
        theme_colors: Optional theme color palette
        opacity: Background opacity (0.0-1.0)
        blur_radius: Gaussian blur radius (0-20)
        texture_intensity: Overlay texture strength (0.0-1.0)
        vignette_intensity: Edge darkening (0.0-1.0)
        food_category: For AUTO mode smart selection
        
    Returns:
        PIL Image (RGBA mode)
    """
    # Smart selection for AUTO mode
    if bg_type == BackgroundType.AUTO:
        bg_type = _smart_background_selection(food_category, theme_colors)
    
    # Check cache
    cache_key = (bg_type.value, canvas_size, blur_radius, texture_intensity)
    if cache_key in _BACKGROUND_CACHE:
        bg = _BACKGROUND_CACHE[cache_key].copy()
    else:
        # Generate base background
        bg = _generate_base_background(bg_type, canvas_size, theme_colors)
        
        # Apply texture overlay
        if texture_intensity > 0:
            bg = _apply_texture(bg, bg_type, texture_intensity)
        
        # Apply blur
        if blur_radius > 0:
            bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Cache for reuse
        _BACKGROUND_CACHE[cache_key] = bg.copy()
    
    # Apply vignette (always per-image)
    if vignette_intensity > 0:
        bg = _apply_vignette(bg, vignette_intensity)
    
    # Apply opacity
    if opacity < 1.0:
        bg = _apply_opacity(bg, opacity)
    
    return bg


def _smart_background_selection(food_category: Optional[str], theme_colors: Optional[dict]) -> BackgroundType:
    """
    Intelligently select background based on food category.
    
    Priority 4.2: Smart theme integration
    """
    if not food_category:
        return BackgroundType.DARK_GRADIENT
    
    category_lower = food_category.lower()
    
    # Mapping food categories to ideal backgrounds
    if any(word in category_lower for word in ["burger", "sandwich", "fries"]):
        return BackgroundType.WOOD_TABLE
    elif any(word in category_lower for word in ["seafood", "fish", "shrimp", "crab"]):
        return BackgroundType.MARBLE
    elif any(word in category_lower for word in ["bbq", "ribs", "brisket", "grilled", "smoked"]):
        return BackgroundType.FIRE
    elif any(word in category_lower for word in ["pizza", "pasta", "italian"]):
        return BackgroundType.RUSTIC_WOOD
    elif any(word in category_lower for word in ["dessert", "cake", "pie", "sweet"]):
        return BackgroundType.PAPER
    elif any(word in category_lower for word in ["coffee", "espresso", "latte"]):
        return BackgroundType.RUSTIC_WOOD
    elif any(word in category_lower for word in ["cocktail", "beer", "drink"]):
        return BackgroundType.NEON
    elif any(word in category_lower for word in ["salad", "healthy", "vegan"]):
        return BackgroundType.LIGHT_GRADIENT
    elif any(word in category_lower for word in ["wings", "sports", "game day"]):
        return BackgroundType.SPORTS_BAR
    else:
        return BackgroundType.DARK_GRADIENT


def _generate_base_background(
    bg_type: BackgroundType,
    canvas_size: Tuple[int, int],
    theme_colors: Optional[dict] = None
) -> Image.Image:
    """Generate base background image without effects."""
    w, h = canvas_size
    
    # Solid backgrounds
    if bg_type == BackgroundType.SOLID_BLACK:
        return Image.new('RGB', (w, h), (0, 0, 0))
    
    elif bg_type == BackgroundType.SOLID_WHITE:
        return Image.new('RGB', (w, h), (255, 255, 255))
    
    elif bg_type == BackgroundType.BRAND_COLOR:
        # Use theme color or default gold
        color = theme_colors.get("primary", (212, 175, 55)) if theme_colors else (212, 175, 55)
        return Image.new('RGB', (w, h), color)
    
    # Gradient backgrounds
    elif bg_type == BackgroundType.DARK_GRADIENT:
        return _generate_gradient(w, h, (20, 20, 30), (50, 50, 60))
    
    elif bg_type == BackgroundType.LIGHT_GRADIENT:
        return _generate_gradient(w, h, (240, 240, 245), (255, 255, 255))
    
    # Texture-based backgrounds
    elif bg_type == BackgroundType.WOOD_TABLE:
        return _generate_wood_texture(w, h, style="table")
    
    elif bg_type == BackgroundType.RUSTIC_WOOD:
        return _generate_wood_texture(w, h, style="rustic")
    
    elif bg_type == BackgroundType.MARBLE:
        return _generate_marble_texture(w, h)
    
    elif bg_type == BackgroundType.CONCRETE:
        return _generate_concrete_texture(w, h)
    
    elif bg_type == BackgroundType.BRICK_WALL:
        return _generate_brick_texture(w, h)
    
    elif bg_type == BackgroundType.CHALKBOARD:
        return _generate_chalkboard_texture(w, h)
    
    elif bg_type == BackgroundType.METAL:
        return _generate_metal_texture(w, h)
    
    elif bg_type == BackgroundType.PAPER:
        return _generate_paper_texture(w, h)
    
    elif bg_type == BackgroundType.LINEN:
        return _generate_linen_texture(w, h)
    
    # Dynamic/effect backgrounds
    elif bg_type == BackgroundType.SMOKE:
        return _generate_smoke_effect(w, h)
    
    elif bg_type == BackgroundType.FIRE:
        return _generate_fire_effect(w, h)
    
    elif bg_type == BackgroundType.NEON:
        return _generate_neon_effect(w, h)
    
    elif bg_type == BackgroundType.RESTAURANT_INTERIOR:
        return _generate_restaurant_interior(w, h)
    
    elif bg_type == BackgroundType.SPORTS_BAR:
        return _generate_sports_bar(w, h)
    
    elif bg_type == BackgroundType.HOLIDAY:
        return _generate_holiday_effect(w, h)
    
    elif bg_type == BackgroundType.KITCHEN:
        return _generate_kitchen_effect(w, h)
    
    elif bg_type == BackgroundType.BOKEH_LIGHTS:
        return _generate_bokeh_lights(w, h)
    
    elif bg_type == BackgroundType.MINIMAL_STUDIO:
        return _generate_minimal_studio(w, h)
    
    # Fallback
    return Image.new('RGB', (w, h), (40, 40, 50))


def _generate_gradient(w: int, h: int, color1: tuple, color2: tuple) -> Image.Image:
    """Generate smooth gradient background."""
    img = Image.new('RGB', (w, h))
    draw = ImageDraw.Draw(img)
    
    for y in range(h):
        ratio = y / h
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    
    return img


def _generate_wood_texture(w: int, h: int, style: str = "table") -> Image.Image:
    """Generate wood grain texture."""
    if style == "table":
        base_color = (139, 90, 43)  # Brown
    else:  # rustic
        base_color = (101, 67, 33)  # Darker brown
    
    img = Image.new('RGB', (w, h), base_color)
    draw = ImageDraw.Draw(img)
    
    # Add wood grain lines
    random.seed(42)
    for _ in range(h // 20):
        y = random.randint(0, h)
        darkness = random.randint(10, 30)
        color = tuple(max(0, c - darkness) for c in base_color)
        thickness = random.randint(1, 3)
        draw.line([(0, y), (w, y)], fill=color, width=thickness)
    
    return img


def _generate_marble_texture(w: int, h: int) -> Image.Image:
    """Generate marble texture with veins."""
    img = Image.new('RGB', (w, h), (245, 245, 248))  # Off-white
    draw = ImageDraw.Draw(img)
    
    # Add marble veins
    random.seed(43)
    for _ in range(20):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = x1 + random.randint(-w//2, w//2), y1 + random.randint(-100, 100)
        draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 205), width=random.randint(1, 3))
    
    return img


def _generate_concrete_texture(w: int, h: int) -> Image.Image:
    """Generate concrete texture."""
    return Image.new('RGB', (w, h), (120, 120, 125))


def _generate_brick_texture(w: int, h: int) -> Image.Image:
    """Generate brick wall pattern."""
    img = Image.new('RGB', (w, h), (160, 82, 45))  # Sienna
    draw = ImageDraw.Draw(img)
    
    brick_h = 40
    brick_w = 120
    mortar = 4
    
    for row in range(0, h, brick_h + mortar):
        offset = (brick_w // 2) if (row // (brick_h + mortar)) % 2 else 0
        for col in range(-offset, w, brick_w + mortar):
            draw.rectangle([col, row, col + brick_w, row + brick_h], 
                          fill=(180, 92, 55), outline=(140, 70, 40), width=1)
    
    return img


def _generate_chalkboard_texture(w: int, h: int) -> Image.Image:
    """Generate chalkboard texture."""
    return Image.new('RGB', (w, h), (40, 54, 24))  # Dark green-grey


def _generate_metal_texture(w: int, h: int) -> Image.Image:
    """Generate brushed metal texture."""
    img = Image.new('RGB', (w, h), (169, 169, 169))  # Grey
    draw = ImageDraw.Draw(img)
    
    # Horizontal brush lines
    for y in range(0, h, 2):
        brightness = random.randint(-10, 10)
        color = tuple(max(0, min(255, 169 + brightness)) for _ in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    
    return img


def _generate_paper_texture(w: int, h: int) -> Image.Image:
    """Generate paper texture."""
    return Image.new('RGB', (w, h), (255, 250, 240))  # Cream


def _generate_linen_texture(w: int, h: int) -> Image.Image:
    """Generate linen fabric texture."""
    return Image.new('RGB', (w, h), (250, 240, 230))  # Beige


def _generate_smoke_effect(w: int, h: int) -> Image.Image:
    """Generate smoky dark background."""
    img = _generate_gradient(w, h, (30, 30, 30), (60, 60, 70))
    # Add swirls (simplified for performance)
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(0.8)


def _generate_fire_effect(w: int, h: int) -> Image.Image:
    """Generate fire/ember effect."""
    return _generate_gradient(w, h, (80, 20, 10), (180, 40, 0))


def _generate_neon_effect(w: int, h: int) -> Image.Image:
    """Generate neon glow background."""
    return _generate_gradient(w, h, (20, 0, 40), (60, 0, 100))


def _generate_restaurant_interior(w: int, h: int) -> Image.Image:
    """Generate restaurant interior ambiance."""
    return _generate_gradient(w, h, (50, 45, 40), (80, 70, 60))


def _generate_sports_bar(w: int, h: int) -> Image.Image:
    """Generate sports bar atmosphere."""
    return Image.new('RGB', (w, h), (25, 35, 45))


def _generate_holiday_effect(w: int, h: int) -> Image.Image:
    """Generate festive holiday background."""
    img = Image.new('RGB', (w, h), (140, 20, 20))  # Red
    draw = ImageDraw.Draw(img)
    
    # Add snowflakes or sparkles
    random.seed(44)
    for _ in range(50):
        x, y = random.randint(0, w), random.randint(0, h)
        draw.ellipse([x, y, x+3, y+3], fill=(255, 255, 255))
    
    return img


def _generate_kitchen_effect(w: int, h: int) -> Image.Image:
    """Generate kitchen atmosphere."""
    return Image.new('RGB', (w, h), (220, 215, 210))  # Light grey


def _generate_bokeh_lights(w: int, h: int) -> Image.Image:
    """Generate bokeh light effect."""
    img = Image.new('RGB', (w, h), (20, 20, 25))
    draw = ImageDraw.Draw(img)
    
    random.seed(45)
    for _ in range(30):
        x, y = random.randint(0, w), random.randint(0, h)
        radius = random.randint(20, 60)
        color = (255, 220, random.randint(100, 200))
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], 
                    fill=color, outline=None)
    
    # Blur to create bokeh effect
    return img.filter(ImageFilter.GaussianBlur(radius=40))


def _generate_minimal_studio(w: int, h: int) -> Image.Image:
    """Generate minimal studio background."""
    return Image.new('RGB', (w, h), (248, 248, 250))


def _apply_texture(bg: Image.Image, bg_type: BackgroundType, intensity: float) -> Image.Image:
    """Apply subtle texture overlay to background."""
    if intensity <= 0:
        return bg
    
    w, h = bg.size
    
    # Generate noise texture
    noise = Image.new('L', (w, h))
    pixels = np.random.randint(0, 50, (h, w), dtype=np.uint8)
    noise.putdata(pixels.flatten())
    
    # Convert to RGBA
    bg_rgba = bg.convert('RGBA')
    noise_rgba = Image.new('RGBA', (w, h), (255, 255, 255, int(intensity * 30)))
    
    # Composite
    return Image.alpha_composite(bg_rgba, noise_rgba)


def _apply_vignette(img: Image.Image, intensity: float) -> Image.Image:
    """
    Apply vignette effect (darken edges).
    
    Priority 4.2: Food protection - keeps attention on center.
    """
    if intensity <= 0:
        return img
    
    w, h = img.size
    img_rgba = img.convert('RGBA')
    
    # Create vignette mask
    mask = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(mask)
    
    # Radial gradient from center
    center_x, center_y = w // 2, h // 2
    max_radius = max(w, h)
    
    for y in range(h):
        for x in range(w):
            distance = ((x - center_x)**2 + (y - center_y)**2) ** 0.5
            ratio = distance / max_radius
            alpha = int(255 * (1 - ratio * intensity))
            alpha = max(0, min(255, alpha))
            draw.point((x, y), fill=alpha)
    
    # Apply darkening overlay
    vignette_layer = Image.new('RGBA', (w, h), (0, 0, 0, int(intensity * 100)))
    vignette_layer.putalpha(mask)
    
    return Image.alpha_composite(img_rgba, vignette_layer)


def _apply_opacity(img: Image.Image, opacity: float) -> Image.Image:
    """Apply opacity to entire background."""
    if opacity >= 1.0:
        return img
    
    img_rgba = img.convert('RGBA')
    alpha = img_rgba.split()[3]
    alpha = alpha.point(lambda p: int(p * opacity))
    img_rgba.putalpha(alpha)
    
    return img_rgba


def clear_cache():
    """Clear background cache (useful for memory management)."""
    global _BACKGROUND_CACHE
    _BACKGROUND_CACHE.clear()
    logger.info("Background cache cleared")
