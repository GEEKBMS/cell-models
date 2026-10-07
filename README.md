# GEEKBMS Cell Models

Stylized **exterior-only** cylindrical Li-ion cell STEP models for mechanical packaging, fixture, and BMS enclosure layout work.

> **Disclaimer（外形参考，非品牌公差副本）**  
> These models are **simplified geometric references** of common cylindrical cell envelopes. They are **not** copies of any manufacturer’s product CAD, branding, or tolerance drawings. Dimensions are nominal envelopes for design layouts. Do not use them as manufacturing or safety certification masters.

## Contents

| Spec   | Envelope (mm) | STEP | Preview |
|--------|---------------|------|---------|
| 18650  | Ø18 × 65      | `cells/18650/18650_geekbms.step` | `preview/18650.png` |
| 21700  | Ø21 × 70      | `cells/21700/21700_geekbms.step` | `preview/21700.png` |
| 26650  | Ø26 × 65      | `cells/26650/26650_geekbms.step` | `preview/26650.png` |
| 4680   | Ø46 × 80      | `cells/4680/4680_geekbms.step`   | `preview/4680.png` |

See `catalog.yaml` for machine-readable metadata.

## Coordinate system

- **Units:** millimetres.
- **Origin:** on the cell axis, at the **negative-end flat** (`z = 0`).
- **+Z:** toward the **positive terminal** (button end).
- **XY:** radial plane; cylinder axis is Z.

```
        +Z (positive terminal / button)
         ↑
         │   ┌─────┐
         │   │ btn │
         │ ┌─┴─────┴─┐
         │ │  wrap   │  ← recessed "GEEKBMS" on side wall
         │ │         │
         │ └─────────┘
         ○────────────→ +X
        z=0  negative end flat (datum)
```

## Assembly datums

Kept clean for mates / fixtures:

1. **Cylinder OD** — nominal envelope diameter (mid-body).
2. **Negative end flat** — planar face at `z = 0`.
3. **Positive end shoulder** — top of wrap body (button sits above it).

Lettering and heat-shrink cues are **recessed into the wrap side wall** so they do not grow the OD or break the end flats.

## Naming rules

- Directory: `cells/<spec>/`
- File: `<spec>_geekbms.step` (lowercase spec token, e.g. `18650_geekbms.step`)
- Preview: `preview/<spec>.png`
- Spec tokens: `18650`, `21700`, `26650`, `4680`

## Geometry notes (what is stylized)

Included (exterior cues only):

- Cylindrical PVC / heat-shrink wrap body at envelope OD.
- Shallow end grooves suggesting wrap tuck.
- Positive button terminal.
- Simple insulator ring recess around the button base.
- Recessed side panel with raised-look **GEEKBMS** engraved lettering.

Not included:

- Internal jelly-roll, tabs, CID, vents, or vent-hole detail.
- Brand logos, trademarks, or photographic wrap art.
- Manufacturer-specific tolerance stacks or surface finishes.

Colors in `catalog.yaml` (`wrap_style_color`, `cap_style_color`) describe the intended mainstream look (blue/green/black wrap + metal caps). Basic STEP export is uncolored solid geometry; apply appearance in your CAD tool as needed.

## Regenerating

```bash
/workspace/.cad_venv/bin/python scripts/make_cells.py
```

Requires CadQuery (OpenCascade). Previews are orthographic/isometric technical schematics via matplotlib (Blender is optional and not required).

## License

MIT — see `LICENSE`.

## Git LFS

`.gitattributes` tracks `*.step` / `*.stp` with Git LFS. Install Git LFS before cloning/pushing binaries.
