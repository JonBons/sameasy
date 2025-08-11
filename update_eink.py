#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps
from waveshare_epd import epd2in7_V2 as epd_mod

# ---------- Paths & assets ----------
BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "last_message.json"
ICON_DIR  = BASE_DIR / "icons" / "material"   # put your PNGs here

# ---------- Icon map (Material Symbols PNGs) ----------
ICON_MAP = {
    # Tests
    "RWT": "test.png", "RMT": "test.png", "NPT": "test.png",
    # Warnings
    "TOR": "tornado.png", "SVR": "thunderstorm.png",
    "FFW": "flood.png", "FLW": "flood.png", "WSW": "snow.png",
    # Watches
    "TOA": "watch.png", "SVA": "watch.png", "FFA": "watch.png",
    # Civil / Amber
    "CAE": "amber.png",
}
FALLBACK_ICON = "info.png"

# ---------- Fonts ----------
FONT_BOLD = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
FONT_REG  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
FONT_SM   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)

# Size for the bottom-left icon on-screen (in pixels, before final rotation)
ICON_BOTTOM_H = 24  # set to 24 (original), or bump to e.g. 28–32 for more presence

# ---------- Helpers ----------
def line_h(font, text="Ag") -> int:
    b = font.getbbox(text)
    return b[3] - b[1]

def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int):
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
    code = (event_code or "").upper().strip()
    name = ICON_MAP.get(code)
    if not name:
        t = (event_title or "").lower()
        if "warning" in t:
            name = "warning.png"
        elif "watch" in t:
            name = "watch.png"
        elif "test" in t:
            name = "test.png"
        else:
            name = FALLBACK_ICON
    return ICON_DIR / name

def load_icon_rgba_on_white(path: Path) -> Image.Image | None:
    """Load RGBA, composite on white to remove transparency cleanly."""
    if not path.exists():
        return None
    img = Image.open(path).convert("RGBA")
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(white, img)     # kills transparency without black fill
    return img.convert("L")                      # grayscale for thresholding

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

def read_payload():
    if not JSON_PATH.exists():
        return {
            "event": "Waiting for alert…",
            "event_code": "",
            "originator": "",
            "source": "",
            "issued_local": "",
            "duration_minutes": "",
            "regions": [],
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    data["regions"] = data.get("regions", []) or []
    return data

# ---------- Render ----------
def render_landscape(img_w: int, img_h: int) -> Image.Image:
    payload = read_payload()
    print(payload)
    event = payload.get("event", "")
    event_code = payload.get("event_code", "")
    originator = payload.get("originator", "")
    source = payload.get("source", "")
    issued_local = payload.get("issued_local", "")
    duration_minutes = payload.get("duration_minutes", "")
    regions_list = payload.get("regions", [])
    updated = payload.get("updated", "")

    # Compose user-visible strings
    second_line = originator if originator else ""
    if source:
        second_line = f"{second_line} ({source})" if second_line else f"({source})"

    third_line = issued_local
    if duration_minutes not in (None, "", 0, "0"):
        third_line = f"{third_line} ({duration_minutes} minutes)".strip()

    regions_text = ", ".join(regions_list)

    # Canvas
    W, H = img_w, img_h
    pad = 10
    x, y = pad, pad
    col_w = W - 2 * pad

    img = Image.new("1", (W, H), 255)
    d = ImageDraw.Draw(img)

    # Title (no icon here anymore)
    d.text((x, y), event, font=FONT_BOLD, fill=0)
    y += line_h(FONT_BOLD, event) + 6

    # Originator (Source)
    if second_line:
        for ln in wrap(d, second_line, FONT_REG, col_w):
            d.text((x, y), ln, font=FONT_REG, fill=0)
            y += line_h(FONT_REG, ln) + 2

    # Separator
    y += 2
    d.line((x, y, x + col_w, y), fill=0, width=1)
    y += 6

    # Issued (Duration)
    if third_line:
        for ln in wrap(d, third_line, FONT_REG, col_w):
            d.text((x, y), ln, font=FONT_REG, fill=0)
            y += line_h(FONT_REG, ln) + 2

    # Regions (smaller font)
    if regions_text:
        for ln in wrap(d, regions_text, FONT_SM, col_w):
            d.text((x, y), ln, font=FONT_SM, fill=0)
            y += line_h(FONT_SM, ln) + 2

    # Footer: Updated (bottom-right)
    footer = f"Updated: {updated}"
    tw = d.textlength(footer, font=FONT_SM)
    d.text((W - pad - tw, H - pad - line_h(FONT_SM, footer)), footer, font=FONT_SM, fill=0)

    # Bottom-left ICON (after text so it overlays if needed)
    icon_path = pick_icon_path(event_code, event)
    icon_l = load_icon_rgba_on_white(icon_path)
    if icon_l:
        icon_1b = to_epd_1bit(icon_l)
        icon_1b = resize_icon_height(icon_1b, ICON_BOTTOM_H)
        ix = pad
        iy = H - pad - icon_1b.height
        img.paste(icon_1b, (ix, iy))

    return img

def main():
    epd = epd_mod.EPD()
    epd.init()      # full refresh (safe for debugging)
    epd.Clear()

    # Panel is portrait; render landscape and rotate 90° CCW
    Wp, Hp = epd.width, epd.height     # e.g., 176 x 264
    W, H = Hp, Wp                      # landscape canvas
    img = render_landscape(W, H).rotate(90, expand=True)

    epd.display(epd.getbuffer(img))
    epd.sleep()

if __name__ == "__main__":
    main()
