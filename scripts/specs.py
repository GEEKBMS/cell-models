"""Shared cylindrical-cell spec table for GEEKBMS cell-models (Plan A).

Pure Python (no CadQuery / Blender imports) so it can be used by:
  - scripts/make_cells.py               (CadQuery clean STEP, cad venv)
  - scripts/blender/make_wrap_decal.py  (system python3 + Pillow)
  - scripts/blender/render_cells.py     (Blender's bundled Python)

All lengths in millimetres. Nominal envelopes: diameter x overall height
(z = 0 negative end flat -> z = height top of positive button).
"""
from __future__ import annotations

import math

# Order = README / catalog order
ORDER = ["18650", "21700", "26650", "4680", "32700", "32140", "40135"]

# Reference template = approved 18650 Plan A (body height 64.2 mm, D 18 mm)
TEMPLATE_BODY_H = 64.2
TEMPLATE_D = 18.0

SPECS: dict[str, dict] = {
    "18650": {
        "diameter": 18.0, "height": 65.0,
        "pos_btn_d": 6.5, "pos_btn_h": 0.8, "insulator_od": 12.0,
        "wrap_color": "blue",
        "wrap_rgb": (33, 71, 163), "stripe_rgb": (22, 62, 158),
        "footer_rgb": (147, 172, 223), "outline_rgb": (12, 24, 60),
    },
    "21700": {
        "diameter": 21.0, "height": 70.0,
        "pos_btn_d": 7.5, "pos_btn_h": 0.9, "insulator_od": 14.0,
        "wrap_color": "green",
        "wrap_rgb": (26, 128, 74), "stripe_rgb": (18, 112, 64),
        "footer_rgb": (150, 210, 172), "outline_rgb": (8, 44, 24),
    },
    "26650": {
        "diameter": 26.0, "height": 65.0,
        "pos_btn_d": 9.0, "pos_btn_h": 0.9, "insulator_od": 17.0,
        "wrap_color": "purple",
        "wrap_rgb": (98, 54, 152), "stripe_rgb": (86, 44, 138),
        "footer_rgb": (196, 172, 226), "outline_rgb": (34, 16, 58),
    },
    "4680": {
        "diameter": 46.0, "height": 80.0,
        "pos_btn_d": 14.0, "pos_btn_h": 1.0, "insulator_od": 28.0,
        "wrap_color": "black",
        "wrap_rgb": (30, 30, 34), "stripe_rgb": (22, 22, 26),
        "footer_rgb": (160, 162, 170), "outline_rgb": (0, 0, 0),
    },
    "32700": {
        "diameter": 32.0, "height": 70.0,
        "pos_btn_d": 10.0, "pos_btn_h": 1.0, "insulator_od": 20.0,
        "wrap_color": "red",
        "wrap_rgb": (176, 32, 38), "stripe_rgb": (156, 24, 30),
        "footer_rgb": (238, 170, 172), "outline_rgb": (60, 8, 10),
    },
    "32140": {
        "diameter": 32.0, "height": 140.0,
        "pos_btn_d": 10.0, "pos_btn_h": 1.0, "insulator_od": 20.0,
        "wrap_color": "teal",
        "wrap_rgb": (0, 122, 134), "stripe_rgb": (0, 106, 118),
        "footer_rgb": (156, 214, 220), "outline_rgb": (0, 40, 46),
    },
    "40135": {
        "diameter": 40.0, "height": 135.0,
        "pos_btn_d": 12.0, "pos_btn_h": 1.0, "insulator_od": 25.0,
        "wrap_color": "orange",
        "wrap_rgb": (206, 98, 22), "stripe_rgb": (188, 86, 16),
        "footer_rgb": (250, 214, 180), "outline_rgb": (80, 34, 4),
    },
}

for _s in SPECS.values():
    _s.setdefault("cap_color", "nickel")


def body_height(spec: dict) -> float:
    """Wrap body height (negative flat to positive shoulder), mm."""
    return float(spec["height"]) - float(spec["pos_btn_h"])


def circumference(spec: dict) -> float:
    return math.pi * float(spec["diameter"])


def label_scale(spec: dict) -> float:
    """Decal scale vs. approved 18650 template, limited by both height and
    diameter so lettering stays proportional on fat or tall cells."""
    return min(body_height(spec) / TEMPLATE_BODY_H, float(spec["diameter"]) / TEMPLATE_D)
