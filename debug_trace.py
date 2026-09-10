"""
debug_trace.py — Data-flow diagnostic for Step 1 of 'create a square'.

Traces:
  1. geometry.requirements_to_operations() output (Builder deterministic path)
  2. geometry.pre_validate_requirements() pre-check
  3. Renderer geometry interpretation (_apply_operations)
  4. Validator pre-check section
  5. Full validate_candidate() result (text-only, no image needed)

Run from project root:
    python debug_trace.py
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from geometry import requirements_to_operations, pre_validate_requirements, line_to_box_parameters
from renderer.scene_renderer import _apply_operations

# ── Synthetic Step 1 planner output ─────────────────────────────────────────
STEP_INSTRUCTION = {
    "step_id": 1,
    "instruction": "Create the first line of the square (bottom edge).",
    "target": "obj_1",
    "requirements": {
        "primitive":  "line",
        "length":     1.0,
        "start":      [0, 0, 0],
        "direction":  [1, 0, 0],
        "thickness":  0.05,
    },
    "is_complete": False,
}

ACCEPTED_STATE = {
    "objects":    [],
    "operations": [],
}

requirements = STEP_INSTRUCTION["requirements"]
target_id    = STEP_INSTRUCTION["target"]

print("=" * 60)
print("DIAGNOSTIC TRACE — Step 1 'create a square'")
print("=" * 60)

# ── 1. geometry.line_to_box_parameters ──────────────────────────────────────
print("\n[1] geometry.line_to_box_parameters()")
params = line_to_box_parameters(
    start=requirements["start"],
    direction=requirements["direction"],
    length=requirements["length"],
    thickness=requirements["thickness"],
)
print(f"    width   = {params['width']}")
print(f"    height  = {params['height']}")
print(f"    depth   = {params['depth']}")
print(f"    center  = {params['center']}")
print(f"    EXPECTED center: [0.5, 0.0, 0.0]")
print(f"    MATCH: {params['center'] == [0.5, 0.0, 0.0]}")

# ── 2. requirements_to_operations ────────────────────────────────────────────
print("\n[2] geometry.requirements_to_operations()")
det_ops = requirements_to_operations(target_id, requirements)
if det_ops is None:
    print("    RETURNED None — deterministic path SKIPPED")
else:
    print(f"    Returned {len(det_ops)} operations:")
    for op in det_ops:
        print(f"      {json.dumps(op)}")

# ── 3. Simulate what the Builder would return ────────────────────────────────
builder_output = {
    "schema_version": "1.0",
    "scene": {"name": "scene", "units": "meters"},
    "operations": det_ops if det_ops else [],
    "constraints": [],
}
candidate_ops = builder_output["operations"]

print("\n[3] Simulated Builder output:")
print(json.dumps(builder_output, indent=2))

# ── 4. Renderer _apply_operations ────────────────────────────────────────────
print("\n[4] Renderer _apply_operations(candidate_ops):")
drawables = _apply_operations(candidate_ops)
if not drawables:
    print("    No drawables produced!")
else:
    for d in drawables:
        print(f"    label={d['label']}  cx={d['cx']}  cy={d['cy']}  cz={d['cz']}  "
              f"w={d['w']}  h={d['h']}  d={d['d']}")
        print(f"    EXPECTED: cx=0.5  cy=0.0  cz=0.0  w=1.0  h=0.05  d=0.05")
        print(f"    cx MATCH: {d['cx'] == 0.5}")
        print(f"    w  MATCH: {d['w']  == 1.0}")
        print(f"    h  MATCH: {d['h']  == 0.05}")

# ── 5. pre_validate_requirements ────────────────────────────────────────────
print("\n[5] geometry.pre_validate_requirements():")
pre_check = pre_validate_requirements(requirements, candidate_ops, target_id)
print(f"    passed = {pre_check['passed']}")
print(f"    notes  = {pre_check['notes']}")
if pre_check.get("issues"):
    print(f"    issues = {pre_check['issues']}")
if pre_check.get("expected"):
    print(f"    expected = {json.dumps(pre_check['expected'], indent=4)}")

# ── 6. Full validate_candidate ───────────────────────────────────────────────
print("\n[6] validate_candidate() — text-only (no image):")
print("    (This calls the LLM — may take a moment...)")
try:
    from validator.qwen_validator import validate_candidate
    result = validate_candidate(
        user_prompt="create a square",
        planner_instruction=STEP_INSTRUCTION,
        scene_state=ACCEPTED_STATE,
        builder_output=builder_output,
        image_path=None,
    )
    print(f"\n    valid      = {result.get('valid')}")
    print(f"    errors     = {json.dumps(result.get('errors', []), indent=4)}")
    print(f"    warnings   = {json.dumps(result.get('warnings', []), indent=4)}")
    print(f"    corrections= {json.dumps(result.get('corrections', []), indent=4)}")
except Exception as e:
    import traceback
    print(f"    EXCEPTION: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("TRACE COMPLETE")
print("=" * 60)
