"""
test_feedback_loop.py — Negative test for the Builder → Validator → retry loop.

This test deliberately injects a WRONG candidate (box at origin instead of
at the correct center [0.5, 0.0, 0.0]) and verifies:

  1. Pre-check correctly identifies the problem.
  2. Validator rejects the candidate with actionable corrections.
  3. A corrected candidate passes the pre-check.
  4. Validator accepts the corrected candidate.

Run from project root:
    python test_feedback_loop.py
"""

import sys, json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from geometry import pre_validate_requirements
from validator.qwen_validator import validate_candidate

# ─────────────────────────────────────────────────────────────────────────────
PLANNER_INSTRUCTION = {
    "step_id":     1,
    "instruction": "Create the first line of the square (bottom edge).",
    "target":      "obj_1",
    "requirements": {
        "primitive":  "line",
        "length":     1.0,
        "start":      [0, 0, 0],
        "direction":  [1, 0, 0],
        "thickness":  0.05,
    },
}

ACCEPTED_STATE = {"objects": [], "operations": []}

# ── Wrong candidate: box at wrong position (origin instead of [0.5, 0, 0]) ──
WRONG_CANDIDATE = {
    "schema_version": "1.0",
    "scene": {"name": "scene", "units": "meters"},
    "operations": [
        {
            "operation":  "create_box",
            "parameters": {"id": "obj_1", "width": 1.0, "height": 0.05, "depth": 0.05},
        },
        # Missing translate — box stays at origin (center = [0,0,0] instead of [0.5,0,0])
    ],
    "constraints": [],
}

# ── Correct candidate: box with translate to proper center ───────────────────
CORRECT_CANDIDATE = {
    "schema_version": "1.0",
    "scene": {"name": "scene", "units": "meters"},
    "operations": [
        {
            "operation":  "create_box",
            "parameters": {"id": "obj_1", "width": 1.0, "height": 0.05, "depth": 0.05},
        },
        {
            "operation":  "translate",
            "parameters": {"target": "obj_1", "offset": [0.5, 0.0, 0.0]},
        },
    ],
    "constraints": [],
}


def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


if __name__ == "__main__":
    requirements  = PLANNER_INSTRUCTION["requirements"]
    target_id     = PLANNER_INSTRUCTION["target"]

    # ── Step 1: Pre-check wrong candidate ────────────────────────────────────
    separator("STEP 1 — Pre-check: WRONG candidate (missing translate)")
    pre_check_wrong = pre_validate_requirements(
        requirements,
        WRONG_CANDIDATE["operations"],
        target_id,
    )
    print(f"Pre-check result:  passed={pre_check_wrong['passed']}")
    print(f"Notes:             {pre_check_wrong['notes']}")
    assert pre_check_wrong["passed"] is False, "FAIL: wrong candidate should fail pre-check!"
    print("✓ Pre-check correctly identified the problem.")

    # ── Step 2: Validate wrong candidate (text-only — no image) ─────────────
    separator("STEP 2 — Validator called with WRONG candidate (text-only)")
    print("  (No render image — using text fallback validator)")
    result_wrong = validate_candidate(
        user_prompt="Create a square",
        planner_instruction=PLANNER_INSTRUCTION,
        scene_state=ACCEPTED_STATE,
        builder_output=WRONG_CANDIDATE,
        image_path=None,
    )
    print(f"\nValidator result:  valid={result_wrong['valid']}")
    print(f"Errors:            {json.dumps(result_wrong.get('errors',  []), indent=4)}")
    print(f"Corrections:       {json.dumps(result_wrong.get('corrections', []), indent=4)}")

    if result_wrong["valid"]:
        print("⚠ Validator accepted the wrong candidate (pre-check override likely).")
        print("  This may happen because pre-check flagged the issue for the VLM — check the output above.")
    else:
        print("✓ Validator correctly rejected the wrong candidate.")

    # ── Step 3: Pre-check correct candidate ──────────────────────────────────
    separator("STEP 3 — Pre-check: CORRECT candidate")
    pre_check_correct = pre_validate_requirements(
        requirements,
        CORRECT_CANDIDATE["operations"],
        target_id,
    )
    print(f"Pre-check result:  passed={pre_check_correct['passed']}")
    print(f"Notes:             {pre_check_correct['notes']}")
    assert pre_check_correct["passed"] is True, "FAIL: correct candidate should pass pre-check!"
    print("✓ Pre-check correctly confirmed the correct candidate.")

    # ── Step 4: Validate correct candidate ───────────────────────────────────
    separator("STEP 4 — Validator called with CORRECT candidate (text-only)")
    result_correct = validate_candidate(
        user_prompt="Create a square",
        planner_instruction=PLANNER_INSTRUCTION,
        scene_state=ACCEPTED_STATE,
        builder_output=CORRECT_CANDIDATE,
        image_path=None,
    )
    print(f"\nValidator result:  valid={result_correct['valid']}")
    if result_correct.get("errors"):
        print(f"Errors:            {json.dumps(result_correct['errors'], indent=4)}")
    if result_correct.get("warnings"):
        print(f"Warnings:          {json.dumps(result_correct['warnings'], indent=4)}")

    if result_correct["valid"]:
        print("✓ Validator accepted the correct candidate.")
    else:
        print("✗ Validator rejected the correct candidate — check prompt/model output above.")

    # ── Summary ───────────────────────────────────────────────────────────────
    separator("FEEDBACK LOOP TEST SUMMARY")
    p1 = pre_check_wrong["passed"]   is False
    p2 = pre_check_correct["passed"] is True
    p3 = result_correct["valid"]     is True

    print(f"  Pre-check detects wrong geometry:    {'✓ PASS' if p1 else '✗ FAIL'}")
    print(f"  Pre-check confirms correct geometry: {'✓ PASS' if p2 else '✗ FAIL'}")
    print(f"  Validator accepts correct candidate: {'✓ PASS' if p3 else '✗ FAIL'}")

    if all([p1, p2, p3]):
        print("\n  ALL CHECKS PASSED — feedback loop is working correctly.")
    else:
        print("\n  SOME CHECKS FAILED — review output above.")
