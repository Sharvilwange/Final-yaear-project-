"""
geometry.py — Deterministic geometry helpers for the AI Procedural 3D system.

Convention (uniform across Builder, Renderer, Validator):
    A "line" = thin create_box whose long axis follows the dominant direction.
    Box center  = midpoint(start, end).
    Renderer:   cx,cy,cz initialise at 0 and translate adds offset — so
                translate([0.5,0,0]) places the box center at x=0.5.

This module is imported by Builder, Validator, and optionally Planner.
It must have NO imports beyond the standard library.
"""

import math

# ── Tolerance for pre-validation (12 cm — generous for LLM geometry) ──────────
TOLERANCE = 0.12


# ─────────────────────────────────────────────────────────────────────────────
# Core conversion helper
# ─────────────────────────────────────────────────────────────────────────────

def line_to_box_parameters(
    start: list,
    direction: list,
    length: float,
    thickness: float = 0.05,
    end: list = None,
) -> dict:
    """
    Compute create_box parameters and translate offset for a line segment.

    Parameters
    ----------
    start     : [x, y, z]   — start point of the line
    direction : [dx, dy, dz] — direction vector (need not be normalised)
    length    : float        — length in metres
    thickness : float        — cross-section size (height and depth for X-lines, etc.)
    end       : [x, y, z]   — optional; overrides start+direction*length

    Returns
    -------
    dict with keys:
        width   — X dimension of the box
        height  — Y dimension
        depth   — Z dimension
        center  — [cx, cy, cz] translate offset (midpoint of start and end)
    """
    start     = [float(v) for v in start]
    direction = [float(v) for v in direction]
    length    = float(length)
    thickness = float(thickness)

    # Normalise direction
    mag = math.sqrt(sum(v * v for v in direction))
    if mag > 1e-9:
        direction = [v / mag for v in direction]

    # Compute end point
    if end is not None:
        end = [float(v) for v in end]
        dx, dy, dz = end[0] - start[0], end[1] - start[1], end[2] - start[2]
        computed_len = math.sqrt(dx * dx + dy * dy + dz * dz)
        if computed_len > 1e-9:
            length    = computed_len
            direction = [dx / computed_len, dy / computed_len, dz / computed_len]
    else:
        end = [round(start[i] + direction[i] * length, 6) for i in range(3)]

    # Centre = midpoint
    cx = round((start[0] + end[0]) / 2, 4)
    cy = round((start[1] + end[1]) / 2, 4)
    cz = round((start[2] + end[2]) / 2, 4)

    # Box dimensions: dominant axis gets the full length; others get thickness
    abs_dir  = [abs(v) for v in direction]
    dominant = abs_dir.index(max(abs_dir))

    length    = round(length,    4)
    thickness = round(thickness, 4)

    if dominant == 0:      # X-axis is the long axis
        w, h, d = length, thickness, thickness
    elif dominant == 1:    # Y-axis is the long axis
        w, h, d = thickness, length, thickness
    else:                  # Z-axis is the long axis
        w, h, d = thickness, thickness, length

    return {"width": w, "height": h, "depth": d, "center": [cx, cy, cz]}


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic requirements → operations
# ─────────────────────────────────────────────────────────────────────────────

def requirements_to_operations(target_id: str, requirements: dict):
    """
    Convert structured Planner requirements to Builder operations.

    Returns a list[dict] of operations when the primitive is recognised,
    or None when the Builder should fall back to LLM generation.
    """
    if not requirements:
        return None

    primitive = str(requirements.get("primitive", "")).lower()

    if primitive in ("line", "edge", "segment", "side"):
        start     = requirements.get("start",     [0.0, 0.0, 0.0])
        direction = requirements.get("direction",  [1.0, 0.0, 0.0])
        length    = float(requirements.get("length",    1.0))
        thickness = float(requirements.get("thickness", 0.05))
        end       = requirements.get("end", None)

        p = line_to_box_parameters(start, direction, length, thickness, end)

        return [
            {
                "operation": "create_box",
                "parameters": {
                    "id":     target_id,
                    "width":  p["width"],
                    "height": p["height"],
                    "depth":  p["depth"],
                }
            },
            {
                "operation": "translate",
                "parameters": {
                    "target": target_id,
                    "offset": p["center"],
                }
            }
        ]

    return None   # unrecognised primitive → caller uses LLM


# ─────────────────────────────────────────────────────────────────────────────
# Mathematical pre-validation
# ─────────────────────────────────────────────────────────────────────────────

def pre_validate_requirements(
    requirements: dict,
    candidate_ops: list,
    target_id: str,
) -> dict:
    """
    Mathematically check candidate operations against Planner requirements.

    Returns
    -------
    dict with:
        passed  : True | False | None  (None = no deterministic check available)
        issues  : list[str]
        notes   : str
        expected: dict  (for VLM prompt context)
    """
    if not requirements:
        return {
            "passed":   None,
            "issues":   [],
            "notes":    "No structured requirements provided.",
            "expected": {},
        }

    primitive = str(requirements.get("primitive", "")).lower()

    if primitive not in ("line", "edge", "segment", "side"):
        return {
            "passed":   None,
            "issues":   [],
            "notes":    f"No deterministic checker for primitive '{primitive}'.",
            "expected": {},
        }

    start     = requirements.get("start",     [0.0, 0.0, 0.0])
    direction = requirements.get("direction",  [1.0, 0.0, 0.0])
    length    = float(requirements.get("length",    1.0))
    thickness = float(requirements.get("thickness", 0.05))
    end       = requirements.get("end", None)

    expected = line_to_box_parameters(start, direction, length, thickness, end)

    # Locate create_box and translate for target_id in candidate_ops
    actual_box    = None
    actual_offset = None
    for op in candidate_ops:
        op_name = op.get("operation", "")
        params  = op.get("parameters", {})
        if op_name == "create_box" and params.get("id") == target_id:
            actual_box = params
        elif op_name == "translate" and params.get("target") == target_id:
            actual_offset = params.get("offset", [0.0, 0.0, 0.0])

    # Build expected description
    half = [expected["width"] / 2, expected["height"] / 2, expected["depth"] / 2]
    approx_start = [round(expected["center"][i] - half[i], 4) for i in range(3)]
    approx_end   = [round(expected["center"][i] + half[i], 4) for i in range(3)]
    exp_desc = {
        "box":         {"width": expected["width"], "height": expected["height"], "depth": expected["depth"]},
        "center":      expected["center"],
        "approx_start": approx_start,
        "approx_end":   approx_end,
        "description": (
            f"Thin box: width={expected['width']} height={expected['height']} depth={expected['depth']}, "
            f"centered at {expected['center']}, "
            f"spanning approx {approx_start} → {approx_end}"
        ),
    }

    # No create_box at all
    if actual_box is None:
        return {
            "passed":   False,
            "issues":   [f"No create_box found for '{target_id}'."],
            "notes":    f"No create_box found for '{target_id}'.",
            "expected": exp_desc,
        }

    issues = []

    # Check dimensions
    for dim, exp_val in [
        ("width",  expected["width"]),
        ("height", expected["height"]),
        ("depth",  expected["depth"]),
    ]:
        act_val = float(actual_box.get(dim, 0.0))
        if abs(act_val - exp_val) > TOLERANCE:
            issues.append(f"{dim}: expected {exp_val:.4f}, got {act_val:.4f}")

    # Check centre / translate offset
    if actual_offset is not None:
        for i, (e_v, a_v) in enumerate(zip(expected["center"], actual_offset)):
            if abs(float(a_v) - float(e_v)) > TOLERANCE:
                issues.append(
                    f"translate offset[{'xyz'[i]}]: expected {e_v:.4f}, got {float(a_v):.4f}"
                )
    else:
        # No translate → box remains at origin (cx=cy=cz=0)
        for i, e_v in enumerate(expected["center"]):
            if abs(float(e_v)) > TOLERANCE:
                issues.append(
                    f"Missing translate; center[{'xyz'[i]}] should be {e_v:.4f} "
                    f"but no translate operation found."
                )

    if issues:
        return {
            "passed":   False,
            "issues":   issues,
            "notes":    "Requirements NOT met: " + "; ".join(issues),
            "expected": exp_desc,
        }

    return {
        "passed":   True,
        "issues":   [],
        "notes":    "All numerical requirements satisfied.",
        "expected": exp_desc,
    }
