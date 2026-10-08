#!/usr/bin/env python3
"""Generate clean exterior cylindrical Li-ion cell STEP models (Plan A, mm).

Plan A:
  - STEP  = clean CadQuery exterior envelope for CAD assembly. NO silkscreen /
            text / label-panel geometry.
  - GLB / PNG = Blender visuals; GEEKBMS branding lives only in the wrap
            texture (see scripts/blender/).

Coordinate system (shared with the Blender scene and README):
  - Origin on cell axis at the negative-end flat (z = 0).
  - +Z toward the positive terminal (button top at z = height).
  - Cylinder OD and both end flats kept as assembly datums.

Usage:
  /workspace/.cad_venv/bin/python scripts/make_cells.py            # all specs
  /workspace/.cad_venv/bin/python scripts/make_cells.py --only 18650
"""

from __future__ import annotations

import sys
from pathlib import Path

import cadquery as cq
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specs import ORDER, SPECS, body_height  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CELLS_DIR = ROOT / "cells"


def _ring_shell(z: float, outer_r: float, inner_r: float, height: float) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .workplane(offset=z)
        .circle(outer_r)
        .circle(inner_r)
        .extrude(height)
    )


def build_cell(name: str, spec: dict) -> cq.Workplane:
    """Build one clean, exterior-only cylindrical cell solid (no label geometry)."""
    D = float(spec["diameter"])
    H = float(spec["height"])
    R = D / 2.0

    pos_btn_d = float(spec["pos_btn_d"])
    pos_btn_h = float(spec["pos_btn_h"])
    insulator_od = float(spec["insulator_od"])

    body_h = body_height(spec)
    wrap_end_margin = max(1.0, 0.06 * H)
    groove_w = 0.35
    groove_d = 0.12

    # Main wrap cylinder — OD is the assembly datum diameter
    cell = cq.Workplane("XY").circle(R).extrude(body_h)

    # Stylized heat-shrink end grooves (side wall only; OD mid-body remains D)
    cell = cell.cut(_ring_shell(wrap_end_margin, R + 0.02, R - groove_d, groove_w))
    cell = cell.cut(
        _ring_shell(body_h - wrap_end_margin - groove_w, R + 0.02, R - groove_d, groove_w)
    )

    # Negative end rim cue on side wall (end flat at z=0 stays planar)
    cell = cell.cut(_ring_shell(0.0, R + 0.02, R - 0.18, 0.22))

    # Positive-end insulator rebate + flush ring (stylized washer look)
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
        "xlen": bb.xlen,
        "ylen": bb.ylen,
        "zlen": bb.zlen,
        "zmin": bb.zmin,
        "zmax": bb.zmax,
        "faces": len(imported.Faces()),
    }


def write_catalog(results: dict[str, dict]) -> None:
    lines = [
        "# GEEKBMS cylindrical cell catalog (Plan A)",
        "# Units: millimetres. Exterior envelope reference only — not a brand tolerance copy.",
        "# STEP = clean CAD envelope (no silkscreen geometry).",
        "# GLB / PNG = Blender visuals; GEEKBMS branding is a wrap texture only.",
        "",
        "units: mm",
        "plan: A",
        "coordinate_system:",
        "  origin: cell axis at negative end flat (z = 0)",
        "  positive_terminal: +Z",
        "  datum_faces:",
        "    - cylinder_od",
        "    - negative_end_flat",
        "    - positive_end_shoulder_plane",
        "glb:",
        "  units: metres (glTF 2.0 standard; 18 mm = 0.018)",
        "  up_axis: +Y (glTF convention; maps to STEP +Z)",
        "  textures: embedded",
        "",
        "cells:",
    ]
    for name in ORDER:
        if name not in results:
            continue
        s = SPECS[name]
        r = results[name]
        lines += [
            f'  - name: "{name}"',
            f"    step: cells/{name}/{name}_geekbms.step",
            f"    glb: cells/{name}/{name}_geekbms.glb",
            f"    preview: preview/{name}.png",
            f"    diameter_mm: {s['diameter']}",
            f"    height_mm: {s['height']}",
            f"    body_height_mm: {body_height(s):.1f}",
            f"    positive_button_diameter_mm: {s['pos_btn_d']}",
            f"    positive_button_height_mm: {s['pos_btn_h']}",
            f"    insulator_od_mm: {s['insulator_od']}",
            f"    wrap_style_color: {s['wrap_color']}",
            f"    cap_style_color: {s['cap_color']}",
            f"    bbox_diameter_mm: {r['xlen']:.3f}",
            f"    bbox_height_mm: {r['zlen']:.3f}",
            f"    step_valid: {str(r['ok']).lower()}",
            "",
        ]
    (ROOT / "catalog.yaml").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build GEEKBMS clean cylindrical cell STEP models")
    parser.add_argument("--only", nargs="+", choices=ORDER, help="Build only these specs")
    parser.add_argument("--out-dir", type=Path, default=CELLS_DIR,
                        help="Output root (default: cells/). Files go to <out>/<spec>/")
    parser.add_argument("--no-catalog", action="store_true", help="Skip rewriting catalog.yaml")
    parser.add_argument("--no-label", action="store_true",
                        help="Accepted for compatibility; Plan A STEP is always label-free")
    args = parser.parse_args(argv)

    names = args.only or ORDER
    results: dict[str, dict] = {}
    for name in names:
        spec = SPECS[name]
        print(f"=== Building {name}  Ø{spec['diameter']:g}×{spec['height']:g} mm ===")
        cell = build_cell(name, spec)
        out_dir = args.out_dir / name
        out_dir.mkdir(parents=True, exist_ok=True)
        step_path = out_dir / f"{name}_geekbms.step"
        cq.exporters.export(cell, str(step_path))
        check = validate_step(step_path, spec["diameter"], spec["height"])
        print(f"  wrote {step_path}  ok={check['ok']} D={check['xlen']:.3f} "
              f"H={check['zlen']:.3f} zmin={check['zmin']:.3f} faces={check['faces']}")
        if not check["ok"]:
            raise SystemExit(f"bbox validation failed for {name}")
        results[name] = check

    if not args.no_catalog and args.out_dir == CELLS_DIR and set(names) == set(ORDER):
        write_catalog(results)
        print("catalog.yaml written")
    print("DONE")


if __name__ == "__main__":
    main()
