#!/usr/bin/env python3
"""Generate stylized exterior cylindrical Li-ion cell STEP models (mm).

Coordinate system (documented in README):
  - Origin on cell axis at the negative-end flat (z=0).
  - +Z toward the positive terminal.
  - Cylinder OD and both end flats kept as assembly datums;
    "GEEKBMS" lettering is recessed into a side-wall panel.
"""

from __future__ import annotations

import math
from pathlib import Path

import cadquery as cq
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader

ROOT = Path(__file__).resolve().parents[1]
CELLS_DIR = ROOT / "cells"
PREVIEW_DIR = ROOT / "preview"

# Nominal envelope (mm): diameter × height
SPECS = {
    "18650": {
        "diameter": 18.0,
        "height": 65.0,
        "pos_btn_d": 6.5,
        "pos_btn_h": 0.8,
        "insulator_od": 12.0,
        "panel_w": 14.0,
        "panel_h": 7.5,
        "text_size": 2.0,
        "wrap_color": "blue",
        "cap_color": "nickel",
    },
    "21700": {
        "diameter": 21.0,
        "height": 70.0,
        "pos_btn_d": 7.5,
        "pos_btn_h": 0.9,
        "insulator_od": 14.0,
        "panel_w": 16.0,
        "panel_h": 8.0,
        "text_size": 2.3,
        "wrap_color": "green",
        "cap_color": "nickel",
    },
    "26650": {
        "diameter": 26.0,
        "height": 65.0,
        "pos_btn_d": 9.0,
        "pos_btn_h": 0.9,
        "insulator_od": 17.0,
        "panel_w": 20.0,
        "panel_h": 8.5,
        "text_size": 2.8,
        "wrap_color": "black",
        "cap_color": "nickel",
    },
    "4680": {
        "diameter": 46.0,
        "height": 80.0,
        "pos_btn_d": 14.0,
        "pos_btn_h": 1.0,
        "insulator_od": 28.0,
        "panel_w": 34.0,
        "panel_h": 12.0,
        "text_size": 4.5,
        "wrap_color": "blue",
        "cap_color": "nickel",
    },
}


def _ring_shell(z: float, outer_r: float, inner_r: float, height: float) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .workplane(offset=z)
        .circle(outer_r)
        .circle(inner_r)
        .extrude(height)
    )


def build_cell(name: str, spec: dict) -> cq.Workplane:
    """Build one stylized exterior-only cylindrical cell solid."""
    D = float(spec["diameter"])
    H = float(spec["height"])
    R = D / 2.0

    pos_btn_d = float(spec["pos_btn_d"])
    pos_btn_h = float(spec["pos_btn_h"])
    insulator_od = float(spec["insulator_od"])
    panel_w = float(spec["panel_w"])
    panel_h = float(spec["panel_h"])
    text_size = float(spec["text_size"])

    body_h = H - pos_btn_h
    wrap_end_margin = max(1.0, 0.06 * H)
    groove_w = 0.35
    groove_d = 0.12
    panel_depth = 0.25
    text_depth = 0.40
    panel_z = body_h * 0.45

    # Main wrap cylinder — OD is the assembly datum diameter
    cell = cq.Workplane("XY").circle(R).extrude(body_h)

    # Stylized heat-shrink end grooves (side wall only; OD mid-body remains D)
    cell = cell.cut(_ring_shell(wrap_end_margin, R + 0.02, R - groove_d, groove_w))
    cell = cell.cut(
        _ring_shell(body_h - wrap_end_margin - groove_w, R + 0.02, R - groove_d, groove_w)
    )

    # Negative end rim cue on side wall (end flat at z=0 stays planar)
    cell = cell.cut(_ring_shell(0.0, R + 0.02, R - 0.18, 0.22))

    # Positive-end insulator rebate + flush ring (stylized PVC/plastic washer look)
    rebate_h = 0.30
    rebate = (
        cq.Workplane("XY")
        .workplane(offset=body_h - rebate_h)
        .circle(insulator_od / 2.0)
        .extrude(rebate_h)
    )
    cell = cell.cut(rebate)
    ring_fill = (
        cq.Workplane("XY")
        .workplane(offset=body_h - rebate_h)
        .circle(insulator_od / 2.0)
        .circle(pos_btn_d / 2.0 + 0.25)
        .extrude(rebate_h - 0.08)
    )
    cell = cell.union(ring_fill)

    # Positive button terminal (protrudes to z=H)
    button = (
        cq.Workplane("XY")
        .workplane(offset=body_h)
        .circle(pos_btn_d / 2.0)
        .extrude(pos_btn_h)
    )
    cell = cell.union(button)

    # Recessed label panel on +X wrap wall (does not increase OD)
    panel_cut = (
        cq.Workplane("YZ")
        .workplane(offset=R)
        .transformed(offset=(0, panel_z, 0))
        .rect(panel_w, panel_h)
        .extrude(-panel_depth)
    )
    cell = cell.cut(panel_cut)

    # Recessed "GEEKBMS" lettering inside the panel
    text_solid = (
        cq.Workplane("YZ")
        .workplane(offset=R - panel_depth)
        .transformed(offset=(0, panel_z, 0))
        .text("GEEKBMS", text_size, -text_depth, font="DejaVu Sans", kind="bold")
    )
    cell = cell.cut(text_solid)

    return cell


def validate_step(path: Path, expect_d: float, expect_h: float, tol: float = 0.05) -> dict:
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed for {path}: {status}")
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape is None or shape.IsNull():
        raise RuntimeError(f"STEP shape null for {path}")

    # Re-import via CadQuery for bbox
    imported = cq.Shape.cast(shape)
    bb = imported.BoundingBox()
    ok = (
        abs(bb.xlen - expect_d) <= tol
        and abs(bb.ylen - expect_d) <= tol
        and abs(bb.zlen - expect_h) <= tol
        and abs(bb.zmin) <= tol
    )
    return {
        "ok": ok,
        "xmin": bb.xmin,
        "xmax": bb.xmax,
        "ymin": bb.ymin,
        "ymax": bb.ymax,
        "zmin": bb.zmin,
        "zmax": bb.zmax,
        "xlen": bb.xlen,
        "ylen": bb.ylen,
        "zlen": bb.zlen,
    }


def render_preview_png(name: str, spec: dict, out_path: Path) -> None:
    """Simple technical isometric schematic (matplotlib) — no brand artwork."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    import numpy as np

    D = spec["diameter"]
    H = spec["height"]
    R = D / 2.0
    btn_r = spec["pos_btn_d"] / 2.0
    btn_h = spec["pos_btn_h"]
    body_h = H - btn_h

    wrap_rgb = {
        "blue": (0.15, 0.35, 0.75),
        "green": (0.12, 0.55, 0.32),
        "black": (0.12, 0.12, 0.14),
    }.get(spec["wrap_color"], (0.15, 0.35, 0.75))
    metal = (0.72, 0.74, 0.76)

    fig = plt.figure(figsize=(6.4, 6.4), dpi=160)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("ortho")

    # Cylinder surface (wrap)
    theta = np.linspace(0, 2 * np.pi, 64)
    z = np.linspace(0, body_h, 40)
    Theta, Z = np.meshgrid(theta, z)
    X = R * np.cos(Theta)
    Y = R * np.sin(Theta)
    ax.plot_surface(X, Y, Z, color=wrap_rgb, linewidth=0, antialiased=True, alpha=0.95, shade=True)

    # Top annulus (metal-ish)
    rr = np.linspace(btn_r + 0.3, R, 12)
    th = np.linspace(0, 2 * np.pi, 48)
    RR, TH = np.meshgrid(rr, th)
    ax.plot_surface(
        RR * np.cos(TH),
        RR * np.sin(TH),
        np.full_like(RR, body_h),
        color=metal,
        linewidth=0,
        alpha=0.95,
        shade=True,
    )

    # Button
    rb = np.linspace(0, btn_r, 10)
    thb = np.linspace(0, 2 * np.pi, 36)
    RB, THB = np.meshgrid(rb, thb)
    ax.plot_surface(
        RB * np.cos(THB),
        RB * np.sin(THB),
        np.full_like(RB, H),
        color=metal,
        linewidth=0,
        alpha=1.0,
        shade=True,
    )
    Zb = np.linspace(body_h, H, 8)
    THS, ZS = np.meshgrid(thb, Zb)
    ax.plot_surface(
        btn_r * np.cos(THS),
        btn_r * np.sin(THS),
        ZS,
        color=metal,
        linewidth=0,
        alpha=1.0,
        shade=True,
    )

    # Bottom flat
    rr0 = np.linspace(0, R, 12)
    RR0, TH0 = np.meshgrid(rr0, th)
    ax.plot_surface(
        RR0 * np.cos(TH0),
        RR0 * np.sin(TH0),
        np.zeros_like(RR0),
        color=metal,
        linewidth=0,
        alpha=0.95,
        shade=True,
    )

    # Label marker on +X
    ax.text(
        R * 0.15,
        0,
        body_h * 0.45,
        "GEEKBMS",
        color="white",
        fontsize=8,
        ha="center",
        va="center",
        fontweight="bold",
    )

    lim = max(D, H) * 0.55
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(0, H)
    ax.set_box_aspect((D, D, H))
    ax.view_init(elev=18, azim=35)
    ax.set_axis_off()
    ax.set_title(f"{name}  Ø{D:g}×{H:g} mm  (exterior ref.)", fontsize=11, pad=8)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def write_catalog(results: list[dict]) -> None:
    lines = [
        "# GEEKBMS cylindrical cell exterior STEP catalog",
        "# Units: millimetres. Exterior envelope reference only.",
        "# Coordinate system: origin on cell axis at negative-end flat (z=0);",
        "# +Z toward positive terminal.",
        "",
        "units: mm",
        "coordinate_system:",
        "  origin: cell axis at negative end flat",
        "  positive_terminal: +Z",
        "  datum_faces:",
        "    - cylinder_od",
        "    - negative_end_flat",
        "    - positive_end_shoulder_plane",
        "",
        "cells:",
    ]
    for r in results:
        s = SPECS[r["name"]]
        lines += [
            f"  - name: {r['name']}",
            f"    file: cells/{r['name']}/{r['name']}_geekbms.step",
            f"    preview: preview/{r['name']}.png",
            f"    diameter_mm: {s['diameter']}",
            f"    height_mm: {s['height']}",
            f"    positive_button_diameter_mm: {s['pos_btn_d']}",
            f"    positive_button_height_mm: {s['pos_btn_h']}",
            f"    wrap_style_color: {s['wrap_color']}",
            f"    cap_style_color: {s['cap_color']}",
            f"    bbox_diameter_mm: {r['bbox']['xlen']:.3f}",
            f"    bbox_height_mm: {r['bbox']['zlen']:.3f}",
            f"    step_valid: {str(r['bbox']['ok']).lower()}",
            "",
        ]
    (ROOT / "catalog.yaml").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    CELLS_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for name, spec in SPECS.items():
        print(f"=== Building {name} ===")
        cell = build_cell(name, spec)
        out_dir = CELLS_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        step_path = out_dir / f"{name}_geekbms.step"
        cq.exporters.export(cell, str(step_path))

        bb = cell.val().BoundingBox()
        print(
            f"  wrote {step_path}\n"
            f"  bbox D≈{bb.xlen:.3f}×{bb.ylen:.3f}, H={bb.zlen:.3f} "
            f"(z {bb.zmin:.3f}..{bb.zmax:.3f})"
        )

        check = validate_step(step_path, spec["diameter"], spec["height"])
        print(f"  reimport ok={check['ok']} D={check['xlen']:.3f} H={check['zlen']:.3f}")

        preview_path = PREVIEW_DIR / f"{name}.png"
        try:
            render_preview_png(name, spec, preview_path)
            print(f"  preview {preview_path}")
            preview_ok = True
        except Exception as exc:  # noqa: BLE001
            print(f"  preview FAILED: {exc}")
            preview_ok = False

        results.append(
            {
                "name": name,
                "step": str(step_path),
                "bbox": check,
                "preview_ok": preview_ok,
            }
        )

    write_catalog(results)
    print("catalog.yaml written")
    print("DONE")


if __name__ == "__main__":
    main()
