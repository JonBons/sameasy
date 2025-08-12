#!/usr/bin/env python3
from pathlib import Path
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from PIL import Image, ImageDraw, ImageFont, ImageOps
from waveshare_epd import epd2in7_V2 as epd_mod

# ---------- Project Setup ----------
PROJECT_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = PROJECT_ROOT / "runtime"
JSON_PATH = PROJECT_ROOT / "runtime" / "last_message.json"
CONFIG_PATH = PROJECT_ROOT / "config.json"
ICON_DIR = PROJECT_ROOT / "icons" / "material"

# Ensure runtime directories exist
RUNTIME_DIR.mkdir(exist_ok=True)
(RUNTIME_DIR / "logs").mkdir(exist_ok=True)

# ---------- Setup logging ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RUNTIME_DIR / 'logs' / 'eink_display.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ---------- Configuration ----------
def load_config() -> Dict[str, Any]:
    """Load configuration from config.json with error handling."""
    try:
        if not CONFIG_PATH.exists():
            logger.error(f"Config file not found: {CONFIG_PATH}")
            raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info("Configuration loaded successfully")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise

# Load configuration
config = load_config()

# ---------- Font initialization with error handling ----------
def load_fonts() -> Dict[str, ImageFont.FreeTypeFont]:
    """Load fonts with error handling."""
    fonts = {}
    font_config = config['fonts']
    font_sizes = config['font_sizes']
    
    for font_type, font_path in font_config.items():
        try:
            size = font_sizes[font_type]
            fonts[font_type] = ImageFont.truetype(font_path, size)
            logger.info(f"Loaded {font_type} font from {font_path}")
        except OSError as e:
            logger.error(f"Failed to load {font_type} font from {font_path}: {e}")
            # Use default font as fallback
            fonts[font_type] = ImageFont.load_default()
            logger.warning(f"Using default font for {font_type}")
    
    return fonts

fonts = load_fonts()
FONT_BOLD = fonts['bold']
FONT_REG = fonts['regular']
FONT_SM = fonts['small']

# Display settings
ICON_BOTTOM_H = config['display']['icon_bottom_height']
PADDING = config['display']['padding']

# ---------- Helpers ----------
def line_h(font, text="Ag") -> int:
    """Get line height for a font."""
    b = font.getbbox(text)
    return b[3] - b[1]

def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int):
    """Wrap text to fit within specified width."""
    if not text:
        return []
    words, lines, buf = text.split(), [], ""
    for w in words:
        t = (buf + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            buf = t
        else:
            if buf:
                lines.append(buf)
            buf = w
    if buf:
        lines.append(buf)
    return lines

def pick_icon_path(event_code: str, event_title: str) -> Path:
    """Pick appropriate icon path based on event code and title."""
    code = (event_code or "").upper().strip()
    icon_mappings = config['icon_mappings']
    fallback_mappings = config['icon_fallbacks']
    fallback_icon = config['fallback_icon']
    
    name = icon_mappings.get(code)
    if not name:
        t = (event_title or "").lower()
        for keyword, icon_name in fallback_mappings.items():
            if keyword in t:
                name = icon_name
                break
        else:
            name = fallback_icon
    
    return ICON_DIR / name

def load_icon_rgba_on_white(path: Path) -> Optional[Image.Image]:
    """Load RGBA, composite on white to remove transparency cleanly."""
    if not path.exists():
        logger.warning(f"Icon file not found: {path}")
        return None
    
    try:
        img = Image.open(path).convert("RGBA")
        white = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(white, img)     # kills transparency without black fill
        return img.convert("L")                      # grayscale for thresholding
    except Exception as e:
        logger.error(f"Error loading icon {path}: {e}")
        return None

def to_epd_1bit(img_l: Image.Image) -> Image.Image:
    """Threshold to hard 1-bit without dithering for crisp lines."""
    # You can tune 128 threshold if needed (e.g., 120–140) depending on icon weight
    return img_l.point(lambda p: 0 if p < 128 else 255).convert("1", dither=Image.NONE)

def resize_icon_height(img_1b: Image.Image, target_h: int) -> Image.Image:
    if target_h <= 0 or img_1b.height == target_h:
        return img_1b
    ratio = target_h / img_1b.height
    w = max(1, int(round(img_1b.width * ratio)))
    return img_1b.resize((w, target_h), Image.NEAREST)

def validate_payload_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize payload data."""
    required_fields = {
        "event": "Waiting for alert…",
        "event_code": "",
        "originator": "",
        "source": "",
        "issued_local": "",
        "duration_minutes": "",
        "regions": [],
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    validated_data = {}
    for field, default_value in required_fields.items():
        value = data.get(field, default_value)
        
        # Type validation
        if field == "regions":
            validated_data[field] = value if isinstance(value, list) else []
        elif field in ["duration_minutes"]:
            # Convert to string, handle None and numeric values
            if value in (None, "", 0, "0"):
                validated_data[field] = ""
            else:
                validated_data[field] = str(value)
        else:
            validated_data[field] = str(value) if value is not None else default_value
    
    return validated_data

def read_payload() -> Dict[str, Any]:
    """Read and validate payload data from JSON file."""
    if not JSON_PATH.exists():
        logger.info("No message file found, using default data")
        return validate_payload_data({})
    
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        logger.info("Message data loaded successfully")
        return validate_payload_data(data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in message file: {e}")
        return validate_payload_data({})
    except Exception as e:
        logger.error(f"Error reading message file: {e}")
        return validate_payload_data({})

# ---------- Render ----------
def compose_display_strings(payload: Dict[str, Any]) -> Dict[str, str]:
    """Compose user-visible strings from payload data."""
    originator = payload["originator"]
    source = payload["source"]
    issued_local = payload["issued_local"]
    duration_minutes = payload["duration_minutes"]
    regions_list = payload["regions"]
    
    # Second line: originator and source
    second_line = originator if originator else ""
    if source:
        second_line = f"{second_line} ({source})" if second_line else f"({source})"
    
    # Third line: issued time and duration
    third_line = issued_local
    if duration_minutes not in ("", "0"):
        third_line = f"{third_line} ({duration_minutes} minutes)".strip()
    
    # Regions text
    regions_text = ", ".join(regions_list) if regions_list else ""
    
    return {
        "second_line": second_line,
        "third_line": third_line,
        "regions_text": regions_text
    }

def render_text_content(img: Image.Image, draw: ImageDraw.ImageDraw, payload: Dict[str, Any], 
                       col_w: int, pad: int) -> int:
    """Render text content and return the final y position."""
    strings = compose_display_strings(payload)
    x, y = pad, pad
    
    # Title
    event = payload["event"]
    draw.text((x, y), event, font=FONT_BOLD, fill=0)
    y += line_h(FONT_BOLD, event) + 6
    
    # Originator (Source)
    if strings["second_line"]:
        for ln in wrap(draw, strings["second_line"], FONT_REG, col_w):
            draw.text((x, y), ln, font=FONT_REG, fill=0)
            y += line_h(FONT_REG, ln) + 2
    
    # Separator
    y += 2
    draw.line((x, y, x + col_w, y), fill=0, width=1)
    y += 6
    
    # Issued (Duration)
    if strings["third_line"]:
        for ln in wrap(draw, strings["third_line"], FONT_REG, col_w):
            draw.text((x, y), ln, font=FONT_REG, fill=0)
            y += line_h(FONT_REG, ln) + 2
    
    # Regions (smaller font)
    if strings["regions_text"]:
        for ln in wrap(draw, strings["regions_text"], FONT_SM, col_w):
            draw.text((x, y), ln, font=FONT_SM, fill=0)
            y += line_h(FONT_SM, ln) + 2
    
    return y

def render_footer_and_icon(img: Image.Image, draw: ImageDraw.ImageDraw, payload: Dict[str, Any], 
                          img_w: int, img_h: int, pad: int) -> None:
    """Render footer timestamp and bottom-left icon."""
    # Footer: Updated (bottom-right)
    footer = f"Updated: {payload['updated']}"
    tw = draw.textlength(footer, font=FONT_SM)
    draw.text((img_w - pad - tw, img_h - pad - line_h(FONT_SM, footer)), footer, font=FONT_SM, fill=0)
    
    # Bottom-left ICON
    icon_path = pick_icon_path(payload["event_code"], payload["event"])
    icon_l = load_icon_rgba_on_white(icon_path)
    if icon_l:
        icon_1b = to_epd_1bit(icon_l)
        icon_1b = resize_icon_height(icon_1b, ICON_BOTTOM_H)
        ix = pad
        iy = img_h - pad - icon_1b.height
        img.paste(icon_1b, (ix, iy))

def render_landscape(img_w: int, img_h: int) -> Image.Image:
    """Main rendering function for landscape layout."""
    payload = read_payload()
    logger.info(f"Rendering display with event: {payload['event']}")
    
    # Canvas setup
    W, H = img_w, img_h
    pad = PADDING
    col_w = W - 2 * pad
    
    img = Image.new("1", (W, H), 255)
    draw = ImageDraw.Draw(img)
    
    # Render components
    render_text_content(img, draw, payload, col_w, pad)
    render_footer_and_icon(img, draw, payload, W, H, pad)
    
    return img

def main():
    """Main function with comprehensive error handling."""
    try:
        logger.info("Initializing e-ink display")
        epd = epd_mod.EPD()
        epd.init()      # full refresh (safe for debugging)
        epd.Clear()
        
        # Panel is portrait; render landscape and rotate 90° CCW
        Wp, Hp = epd.width, epd.height     # e.g., 176 x 264
        W, H = Hp, Wp                      # landscape canvas
        
        logger.info(f"Rendering image for display ({W}x{H})")
        img = render_landscape(W, H).rotate(90, expand=True)
        
        logger.info("Displaying image on e-ink screen")
        epd.display(epd.getbuffer(img))
        epd.sleep()
        
        logger.info("Display update completed successfully")
        
    except Exception as e:
        logger.error(f"Error during display update: {e}")
        try:
            # Attempt to safely shut down the display
            if 'epd' in locals():
                epd.sleep()
        except:
            logger.error("Failed to safely shut down e-ink display")
        raise

if __name__ == "__main__":
    main()
