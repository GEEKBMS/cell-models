"""Headless Blender (4.3) Plan A renders + textured GLB for all cylindrical cells.

Generalized from the approved 18650 Plan A scene:
  - PVC wrap = side-wall cylinder with UV decal (GEEKBMS vertical along +Z,
    footer www.geekbms.com); nickel end caps, insulator washer, button.
  - Cycles CPU, denoise off (Debian Blender has no OpenImageDenoise).
  - Camera / lights / floor scale with the cell so framing stays consistent.

Outputs per spec:
  preview/<spec>.png                 Cycles render (label facing camera, +X)
  cells/<spec>/<spec>_geekbms.glb    textures embedded, metres, glTF +Y up

Prerequisite (system python3, NOT Blender's Python):
  python3 scripts/blender/make_wrap_decal.py     # -> build/decals/<spec>_wrap_decal.png

Run:
  blender --background --python scripts/blender/render_cells.py -- \
      [--only 18650 21700] [--samples 96] [--res 1200] [--no-render] [--no-export] [--blend]
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from specs import ORDER, SPECS, body_height  # noqa: E402

ROOT = HERE.parents[1]
DECAL_DIR = ROOT / "build" / "decals"
PREVIEW_DIR = ROOT / "preview"
CELLS_DIR = ROOT / "cells"
U_OFF = 0.75  # from UV probe: centres decal u=0.5 on +X (camera side)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def set_mm_units():
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 0.001
    s.unit_settings.length_unit = "MILLIMETERS"


def principled(name, color, metallic=0.0, roughness=0.45):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def wrap_material(path: Path, name: str):
    mat = bpy.data.materials.new(f"PVCWrap_{name}")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(path))
    img.name = f"{name}_wrap_decal"
    tex.image = img
    tex.interpolation = "Cubic"
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.42
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.4
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def add_cyl(name, radius, depth, z_center, verts=128):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=radius, depth=depth, location=(0, 0, z_center), calc_uvs=True
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
    except Exception:  # noqa: BLE001
        pass
    return obj


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def delete_caps(obj):
    """Keep side wall only so the wrap texture doesn't paint the ends."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if abs(f.normal.z) > 0.9], context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def shift_uv(obj, u_off):
    """Primitive cylinder side UVs use V in [0.5, 1]; remap to [0, 1] so the
    full-height wrap texture covers the wall, then rotate U by u_off."""
    uv = obj.data.uv_layers.active
    for loop in obj.data.loops:
        co = uv.data[loop.index].uv
        if co.y >= 0.5:
            co.y = (co.y - 0.5) * 2.0
        co.x = (co.x + u_off) % 1.0


def build(name: str, spec: dict, wrap_mat, metal, plastic):
    D, H = float(spec["diameter"]), float(spec["height"])
    R = D / 2.0
    body_h = body_height(spec)
    btn_d, btn_h = float(spec["pos_btn_d"]), float(spec["pos_btn_h"])
    ins_od = float(spec["insulator_od"])
    margin = max(1.0, 0.06 * H)
    p = f"{name}_"

    body = add_cyl(p + "WrapBody", R, body_h, body_h / 2.0, verts=192)
    assign(body, wrap_mat)
    delete_caps(body)
    shift_uv(body, U_OFF)

    assign(add_cyl(p + "NegCap", R - 0.02, 0.5, 0.25, verts=128), metal)
    assign(add_cyl(p + "PosShoulder", R - 0.04, 0.7, body_h - 0.35, verts=128), metal)
    assign(add_cyl(p + "Insulator", ins_od / 2.0, 0.32, body_h - 0.10, verts=96), plastic)
    # Button kept at the true STEP height so the GLB envelope == STEP envelope
    assign(add_cyl(p + "PosButton", btn_d / 2.0, btn_h, body_h + btn_h / 2.0, verts=96), metal)
    groove = principled(p + "Groove", (0.06, 0.09, 0.16), metallic=0.05, roughness=0.65)
    for i, zc in enumerate((margin + 0.18, body_h - margin - 0.18)):
        assign(add_cyl(f"{p}Groove{i}", R * 0.988, 0.32, zc, verts=128), groove)


def framing_scale(spec: dict) -> float:
    """1.0 for the 18650 template; grows with height (or diameter for squat cells)."""
    return max(float(spec["height"]) / 65.0, float(spec["diameter"]) / 40.0)


def stage(spec: dict, k: float, samples: int, res: int):
    sc = bpy.context.scene
    world = bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.22, 0.23, 0.26, 1.0)
    bg.inputs["Strength"].default_value = 0.55

    def area(loc, energy, size, rot, color):
        bpy.ops.object.light_add(type="AREA", location=tuple(c * k for c in loc))
        o = bpy.context.active_object
        o.data.energy = energy * k * k  # keep irradiance constant as the rig scales
        o.data.size = size * k
        o.data.color = color
        o.rotation_euler = Euler(rot, "XYZ")

    area((50, -25, 55), 320000, 45, (math.radians(60), 0, math.radians(35)), (1.0, 0.98, 0.95))
    area((-35, 40, 35), 140000, 55, (math.radians(50), 0, math.radians(-40)), (0.8, 0.85, 1.0))
    area((20, 60, 90), 90000, 40, (math.radians(30), 0, math.radians(180)), (1, 1, 1))

    bpy.ops.mesh.primitive_plane_add(size=500 * k, location=(0, 0, -0.02))
    floor = bpy.context.active_object
    floor.name = "Floor"
    assign(floor, principled("FloorMat", (0.55, 0.56, 0.58), roughness=0.92))

    H = float(spec["height"])
    loc, look = (150 * k, 0.0, H * 0.55), (0, 0, H * 0.38)
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.name = "CamFront"
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 55
    cam.data.clip_start = 1.0
    cam.data.clip_end = 5000.0 * k
    sc.camera = cam

    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.film_transparent = False


def export_glb(name: str, path: Path):
    """Strip stage, convert mm -> metres, export single GLB with embedded texture."""
    for o in list(bpy.data.objects):
        if o.type != "MESH" or o.name == "Floor":
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.data.objects:
        o.location = o.location * 0.001
        o.scale = o.scale * 0.001
        o.select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[0]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for img in bpy.data.images:
        if img.filepath and not img.packed_file:
            img.pack()
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    print("EXPORTED_GLB", path, "bytes", path.stat().st_size)


def run_one(name: str, samples: int, res: int, do_render: bool, do_export: bool, blend: bool):
    spec = SPECS[name]
    decal = DECAL_DIR / f"{name}_wrap_decal.png"
    if not decal.exists():
        raise SystemExit(f"missing {decal}; run: python3 scripts/blender/make_wrap_decal.py")
    clear_scene()
    set_mm_units()
    wrap = wrap_material(decal, name)
    metal = principled("Nickel", (0.78, 0.80, 0.82), metallic=1.0, roughness=0.22)
    plastic = principled("Insulator", (0.93, 0.94, 0.96), metallic=0.0, roughness=0.55)
    build(name, spec, wrap, metal, plastic)
    stage(spec, framing_scale(spec), samples, res)

    if do_render:
        out = PREVIEW_DIR / f"{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        bpy.context.scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {out} in {time.time() - t0:.1f}s")
    if blend:
        bp = ROOT / "build" / "blend" / f"{name}_geekbms.blend"
        bp.parent.mkdir(parents=True, exist_ok=True)
        for img in bpy.data.images:
            if img.filepath and not img.packed_file:
                img.pack()
        bpy.ops.wm.save_as_mainfile(filepath=str(bp), compress=True, copy=True)
        print("SAVED_BLEND", bp)
    if do_export:
        export_glb(name, CELLS_DIR / name / f"{name}_geekbms.glb")


def main():
    import argparse

    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="+", choices=ORDER)
    p.add_argument("--samples", type=int, default=96)
    p.add_argument("--res", type=int, default=1200)
    p.add_argument("--no-render", action="store_true")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--blend", action="store_true", help="also save build/blend/<spec>_geekbms.blend")
    a = p.parse_args(argv)
    for name in a.only or ORDER:
        print(f"=== {name} ===")
        run_one(name, a.samples, a.res, not a.no_render, not a.no_export, a.blend)
    print("DONE Blender Plan A", bpy.app.version_string)


if __name__ == "__main__":
    main()
