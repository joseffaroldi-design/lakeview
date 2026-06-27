"""
FlyerCustomizationConfig — Single source of truth for flyer rendering.

Priority 4: All renderers (PIL, HTML, future AI) consume this unified config.
This eliminates parameter sprawl and ensures consistency across render engines.
"""

from dataclasses import dataclass, field
from typing import Optional, Literal, Tuple
from enum import Enum


class LogoPlacement(str, Enum):
    """Logo positioning options."""
    NONE = "none"
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
    WATERMARK = "watermark"  # Centered, semi-transparent


class LogoSize(str, Enum):
    """Logo size options."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class BackgroundType(str, Enum):
    """Background preset types - Priority 4.2 expanded."""
    AUTO = "auto"  # Smart selection based on food category
    SOLID_BLACK = "solid_black"
    SOLID_WHITE = "solid_white"
    BRAND_COLOR = "brand_color"
    DARK_GRADIENT = "dark_gradient"
    LIGHT_GRADIENT = "light_gradient"
    WOOD_TABLE = "wood_table"
    RUSTIC_WOOD = "rustic_wood"
    MARBLE = "marble"
    CONCRETE = "concrete"
    BRICK_WALL = "brick_wall"
    CHALKBOARD = "chalkboard"
    METAL = "metal"
    PAPER = "paper"
    LINEN = "linen"
    SMOKE = "smoke"
    FIRE = "fire"
    NEON = "neon"
    RESTAURANT_INTERIOR = "restaurant_interior"
    SPORTS_BAR = "sports_bar"
    HOLIDAY = "holiday"
    KITCHEN = "kitchen"
    BOKEH_LIGHTS = "bokeh_lights"
    MINIMAL_STUDIO = "minimal_studio"
    CUSTOM = "custom"  # User-uploaded


@dataclass
class FlyerCustomizationConfig:
    """
    Unified configuration for flyer generation.
    
    All renderers (PIL, HTML, future AI) consume this config to ensure
    consistent rendering across different engines.
    """
    
    # === Core Content ===
    item_name: str
    features: list[str] = field(default_factory=list)
    price: Optional[str] = None
    
    # === Visual Theme ===
    theme: str = "modern"
    background_type: BackgroundType = BackgroundType.AUTO
    background_custom_url: Optional[str] = None  # For custom backgrounds
    background_opacity: float = 1.0  # 0.0 to 1.0
    background_blur: int = 0  # Gaussian blur radius (0-20)
    vignette_intensity: float = 0.3  # 0.0 to 1.0 (darkens edges)
    texture_intensity: float = 0.5  # 0.0 to 1.0 (overlay texture strength)
    
    # === Logo Configuration ===
    logo_url: Optional[str] = None  # URL to logo image
    logo_placement: LogoPlacement = LogoPlacement.NONE
    logo_size: LogoSize = LogoSize.MEDIUM
    
    # === Layout & Typography ===
    layout: str = "centered"  # centered, asym_left, stacked
    typography_variant: Optional[str] = None  # Font style override
    
    # === Platform & Dimensions ===
    platform: str = "instagram_post"
    canvas_width: int = 1024
    canvas_height: int = 1024
    
    # === Marketing Copy ===
    tone: Optional[str] = None  # professional, casual, luxury, bold, playful
    marketing_goal: Optional[str] = None  # drive_traffic, promote_item, etc.
    caption_length: Optional[str] = None  # short, medium, long
    cta: Optional[str] = None  # Call-to-action text
    
    # === Content Flags ===
    include_price: bool = True
    include_description: bool = True
    remove_background: bool = False  # Food background removal
    
    # === Variant/Generation ===
    variant_idx: int = 0  # Which variant (0-4 for A-E)
    variations: int = 3  # How many variants to generate
    
    # === Advanced Customization ===
    border_style: Optional[str] = None  # Future: rounded, sharp, none
    decorations: list[str] = field(default_factory=list)  # Future: icons, shapes
    color_palette_override: Optional[dict] = None  # Future: custom colors
    
    # === Branding ===
    restaurant_name: str = "Lakeview Burgers & Seafood"
    
    def get_logo_coordinates(self) -> Tuple[int, int]:
        """
        Calculate logo position based on placement and canvas size.
        Returns (x, y) tuple for top-left corner of logo.
        """
        # Safe margin from edges
        margin = 30
        
        # Logo dimensions (will scale based on size)
        logo_width = {
            LogoSize.SMALL: 80,
            LogoSize.MEDIUM: 120,
            LogoSize.LARGE: 180,
        }.get(self.logo_size, 120)
        
        logo_height = logo_width  # Assume square for now
        
        # Calculate positions
        center_x = (self.canvas_width - logo_width) // 2
        right_x = self.canvas_width - logo_width - margin
        center_y = (self.canvas_height - logo_height) // 2
        bottom_y = self.canvas_height - logo_height - margin
        
        positions = {
            LogoPlacement.TOP_LEFT: (margin, margin),
            LogoPlacement.TOP_CENTER: (center_x, margin),
            LogoPlacement.TOP_RIGHT: (right_x, margin),
            LogoPlacement.BOTTOM_LEFT: (margin, bottom_y),
            LogoPlacement.BOTTOM_CENTER: (center_x, bottom_y),
            LogoPlacement.BOTTOM_RIGHT: (right_x, bottom_y),
            LogoPlacement.WATERMARK: (center_x, center_y),
            LogoPlacement.NONE: (-1, -1),  # Off-screen
        }
        
        return positions.get(self.logo_placement, (-1, -1))
    
    def get_logo_alpha(self) -> int:
        """Return logo opacity (0-255) based on placement."""
        if self.logo_placement == LogoPlacement.WATERMARK:
            return 77  # ~30% opacity for watermarks
        return 255  # Full opacity otherwise
    
    def get_logo_max_size(self) -> Tuple[int, int]:
        """Return maximum logo dimensions (width, height)."""
        sizes = {
            LogoSize.SMALL: (80, 80),
            LogoSize.MEDIUM: (120, 120),
            LogoSize.LARGE: (180, 180),
        }
        return sizes.get(self.logo_size, (120, 120))
    
    @classmethod
    def from_generate_request(cls, req: dict, platform_size: Tuple[int, int]) -> "FlyerCustomizationConfig":
        """
        Factory method to create config from API request.
        
        This bridges the API layer to the rendering layer.
        """
        from flyer_config import BackgroundType, LogoPlacement, LogoSize
        
        return cls(
            item_name=req.get("item_name", ""),
            features=req.get("features", []),
            price=req.get("price"),
            theme=req.get("theme", "modern"),
            background_type=BackgroundType(req.get("background_type", "auto")),
            background_custom_url=req.get("background_custom_url"),
            logo_url=req.get("logo_url"),
            logo_placement=LogoPlacement(req.get("logo_placement", "none")),
            logo_size=LogoSize(req.get("logo_size", "medium")),
            layout=req.get("layout", "centered"),
            platform=req.get("platform", "instagram_post"),
            canvas_width=platform_size[0],
            canvas_height=platform_size[1],
            tone=req.get("tone"),
            marketing_goal=req.get("marketing_goal"),
            caption_length=req.get("caption_length"),
            cta=req.get("cta"),
            include_price=req.get("include_price", True),
            include_description=req.get("include_description", True),
            remove_background=req.get("remove_background", False),
            variant_idx=req.get("variant_idx", 0),
            variations=req.get("variations", 3),
            restaurant_name=req.get("restaurant_name", "Lakeview Burgers & Seafood"),
        )
