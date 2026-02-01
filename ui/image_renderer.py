"""
VisionGuard AI - Debug UI Image Renderer

Renders frame snapshots with bounding box overlays.
Uses PIL/Pillow for image handling.
"""

import base64
import io
from typing import Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont
import logging

logger = logging.getLogger(__name__)


# Color map for different event types
EVENT_COLORS = {
    "weapon": (255, 0, 0),        # Red
    "fire": (255, 128, 0),        # Orange
    "fall": (255, 255, 0),        # Yellow
    "person": (0, 255, 0),        # Green
    "crowd": (0, 255, 255),       # Cyan
    "unknown": (128, 128, 128),   # Gray
}


def decode_frame(frame_base64: Optional[str]) -> Optional[Image.Image]:
    """
    Decode base64 frame to PIL Image.
    
    Args:
        frame_base64: Base64 encoded image data
        
    Returns:
        PIL Image or None if decoding fails
    """
    if not frame_base64:
        return None
    
    try:
        # Handle data URL prefix if present
        if "," in frame_base64:
            frame_base64 = frame_base64.split(",", 1)[1]
        
        image_data = base64.b64decode(frame_base64)
        image = Image.open(io.BytesIO(image_data))
        return image.convert("RGB")
    except Exception as e:
        logger.warning(f"Failed to decode frame: {e}")
        return None


def draw_bbox(
    image: Image.Image,
    bbox: List[float],
    label: str = "",
    color: Tuple[int, int, int] = (255, 0, 0),
    line_width: int = 3
) -> Image.Image:
    """
    Draw bounding box on image.
    
    Args:
        image: PIL Image
        bbox: [x1, y1, x2, y2] or [x, y, width, height]
        label: Text label to display
        color: RGB color tuple
        line_width: Box line width
        
    Returns:
        Image with bbox drawn
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)
    
    # Handle both formats
    if len(bbox) >= 4:
        x1, y1, x2, y2 = bbox[:4]
        
        # If x2 < x1, assume [x, y, width, height] format
        if x2 < x1 or y2 < y1:
            x1, y1, w, h = bbox[:4]
            x2, y2 = x1 + w, y1 + h
        
        # Scale if normalized (0-1 range)
        if max(x1, y1, x2, y2) <= 1.0:
            w, h = img.size
            x1, x2 = x1 * w, x2 * w
            y1, y2 = y1 * h, y2 * h
        
        # Draw rectangle
        draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)
        
        # Draw label
        if label:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            except:
                font = ImageFont.load_default()
            
            # Background for text
            text_bbox = draw.textbbox((x1, y1 - 20), label, font=font)
            draw.rectangle(text_bbox, fill=color)
            draw.text((x1, y1 - 20), label, fill=(255, 255, 255), font=font)
    
    return img


def render_event_frame(
    frame_base64: Optional[str],
    bbox: Optional[List[float]] = None,
    event_type: str = "unknown",
    confidence: float = 0.0
) -> Optional[Image.Image]:
    """
    Render event frame with bounding box overlay.
    
    Args:
        frame_base64: Base64 encoded frame
        bbox: Bounding box coordinates
        event_type: Event type for color selection
        confidence: Confidence score for label
        
    Returns:
        Rendered PIL Image or None
    """
    image = decode_frame(frame_base64)
    if image is None:
        return None
    
    if bbox:
        color = EVENT_COLORS.get(event_type.lower(), EVENT_COLORS["unknown"])
        label = f"{event_type} ({confidence:.1%})"
        image = draw_bbox(image, bbox, label=label, color=color)
    
    return image


def create_placeholder_image(
    width: int = 640,
    height: int = 480,
    message: str = "No Frame Available"
) -> Image.Image:
    """Create a placeholder image when frame is unavailable."""
    img = Image.new("RGB", (width, height), color=(40, 40, 50))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    # Center text
    text_bbox = draw.textbbox((0, 0), message, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), message, fill=(100, 100, 120), font=font)
    
    return img


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Convert PIL Image to bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return buffer.getvalue()
