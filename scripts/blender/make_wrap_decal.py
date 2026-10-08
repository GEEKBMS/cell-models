"""Generate Plan A PVC-wrap UV decals (vertical GEEKBMS + footer URL) per spec.

IMPORTANT: Run with system Python (python3 + Pillow), NOT Blender's Python.
Blender's FreeType/PIL build returns broken negative advance metrics, so text
drawn inside Blender lands off-canvas (and wipes the footer).

Texture layout (matches scripts/blender/render_cells.py UVs):
  - Width  (U) = full wrap circumference  (pi * D)  — isotropic px/mm
  - Height (V) = wrap body height; image top = +Z (positive end)
  - Horizontal centre (u = 0.5) faces +X in the Blender scene
  - "GEEKBMS": bold white, dark outline, reading bottom -> top along the cell
    axis, centred on body mid-height
  - Footer "www.geekbms.com": circumferential, lighter tint, below the brand

Letter sizes follow the approved 18650 template scaled by specs.label_scale()
(limited by both diameter and height).

Usage:
  python3 scripts/blender/make_wrap_decal.py                 # all specs -> build/decals/
  python3 scripts/blender/make_wrap_decal.py --only 18650 --out-dir /tmp/x
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from specs import ORDER, SPECS, body_height, circumference, label_scale  # noqa: E402

ROOT = HERE.parents[1]
DEFAULT_OUT = ROOT / "build" / "decals"

BRAND = "GEEKBMS"
FOOTER = "www.geekbms.com"

# Approved 18650 template dimensions (mm on the wrap)
BRAND_LEN_MM = 35.0       # brand length along the axis
FOOTER_W_MM = 11.6        # footer width around the circumference
FOOTER_GAP_MM = 3.7       # brand bottom -> footer centre
STRIPE_PERIOD_MM = 1.55
STRIPE_LIGHT_MM = 0.50
OUTLINE_MM = 0.07
MAX_PX = 4096
MAX_PX_PER_MM = 36.0

BRAND_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
FOOTER_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _font(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    raise RuntimeError(f"No usable font among {paths}")


def _ink_bbox(font: ImageFont.FreeTypeFont, text: str, stroke: int = 0) -> tuple[int, int, int, int]:
    """Glyph ink bbox; raise if FreeType metrics look broken (Blender PIL)."""
    bbox = font.getbbox(text, stroke_width=stroke)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if w <= 0 or h <= 0 or font.getlength(text) <= 0 or bbox[0] < -100:
        raise RuntimeError(
            f"Broken font metrics for {text!r}: bbox={bbox}. "
            "Run this script with system python3, not Blender's Python."
        )
    return bbox


def _fit_font(paths, text, target_w_px, stroke=0):
    size = 100
    f = _font(paths, size)
    b = _ink_bbox(f, text, stroke)
    size = max(8, int(round(size * target_w_px / (b[2] - b[0]))))
    return _font(paths, size)


def build_decal(name: str, footer: str = FOOTER) -> Image.Image:
    spec = SPECS[name]
    C = circumference(spec)
    Hb = body_height(spec)
    ppm = min(MAX_PX_PER_MM, MAX_PX / max(C, Hb))
    W, Hpx = int(round(C * ppm)), int(round(Hb * ppm))
    s = label_scale(spec)
    base, stripe = tuple(spec["wrap_rgb"]), tuple(spec["stripe_rgb"])

    img = Image.new("RGBA", (W, Hpx), (*base, 255))
    draw = ImageDraw.Draw(img)
    period, light = STRIPE_PERIOD_MM * ppm, STRIPE_LIGHT_MM * ppm
    x = 0.0
    while x < W:  # darker stripe band after each light band
        draw.rectangle([int(round(x + light)), 0, int(round(x + period)) - 1, Hpx], fill=(*stripe, 255))
        x += period

    cx = W / 2.0
    mid_y = Hpx / 2.0  # body mid-height

    # --- Brand: render horizontally, rotate 90° CCW -> reads bottom-to-top
    stroke = max(2, int(round(OUTLINE_MM * ppm)))
    brand_len_px = BRAND_LEN_MM * s * ppm
    font = _fit_font(BRAND_FONTS, BRAND, brand_len_px, stroke)
    bb = _ink_bbox(font, BRAND, stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    layer = Image.new("RGBA", (tw + 8, th + 8), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(
        (4 - bb[0], 4 - bb[1]), BRAND, font=font, fill=(255, 255, 255, 255),
        stroke_width=stroke, stroke_fill=(*spec["outline_rgb"], 255),
    )
    layer = layer.rotate(90, expand=True)
    img.alpha_composite(layer, (int(round(cx - layer.width / 2)), int(round(mid_y - layer.height / 2))))
    brand_bottom_y = mid_y + tw / 2.0

    # --- Footer: circumferential URL below the brand
    ffont = _fit_font(FOOTER_FONTS, footer, FOOTER_W_MM * s * ppm)
    fb = _ink_bbox(ffont, footer)
    fw, fh = fb[2] - fb[0], fb[3] - fb[1]
    fcy = brand_bottom_y + FOOTER_GAP_MM * s * ppm
    fcy = min(fcy, Hpx - (max(1.0, 0.06 * spec["height"]) + 1.5) * ppm)  # stay off end groove
    draw = ImageDraw.Draw(img)
    draw.text((cx - fw / 2 - fb[0], fcy - fh / 2 - fb[1]), footer, font=ffont, fill=(*spec["footer_rgb"], 255))
    return img


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Build Plan A wrap decals")
    p.add_argument("--only", nargs="+", choices=ORDER)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--footer", default=FOOTER)
    a = p.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for name in a.only or ORDER:
        img = build_decal(name, a.footer)
        out = a.out_dir / f"{name}_wrap_decal.png"
        img.convert("RGB").save(out, "PNG", optimize=True)
        print("WROTE", out, img.size, "bytes", out.stat().st_size)


if __name__ == "__main__":
    main()
