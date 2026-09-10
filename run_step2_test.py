"""
run_step2_test.py  --  Step 2 diagnostic for 'create a square'.

Runs construction loop max_steps=2, max_retries=3.
Prints verbose output for each stage.
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import core.construction_loop as cl
cl.MAX_RETRIES = 3

from core.construction_loop import run_construction_loop
from state.scene_registry import SceneRegistry

# ── helpers ─────────────────────────────────────────────────────────────────

def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

def check(label, condition, got=None):
    status = "[PASS]" if condition else "[FAIL]"
    msg = f"{status}  {label}"
    if not condition and got is not None:
        msg += f"  (got: {got})"
    print(msg)
    return condition

# ── Run the loop ─────────────────────────────────────────────────────────────

section("END-TO-END TEST: 'create a square'  max_steps=2  max_retries=3")

final_state = run_construction_loop(
    user_prompt="create a square",
    max_steps=2,
    scene_id="test_step2",
)

# ── Analyse final state ───────────────────────────────────────────────────────

section("FINAL STATE")
objects          = final_state.get("objects", [])
ops              = final_state.get("operations", [])
completed_steps  = final_state.get("completed_steps", [])

print(json.dumps({
    "status":           final_state.get("status"),
    "stage":            final_state.get("stage"),
    "objects":          objects,
    "completed_steps":  completed_steps,
    "total_operations": len(ops),
    "operations":       ops,
}, indent=2))

# ── Geometry helpers ─────────────────────────────────────────────────────────

def get_box(obj_id):
    """Return create_box params for obj_id from accepted ops."""
    return next((o["parameters"] for o in ops
                 if o.get("operation") == "create_box"
                 and o.get("parameters", {}).get("id") == obj_id), None)

def get_translate(obj_id):
    """Return translate offset for obj_id from accepted ops."""
    return next((o["parameters"].get("offset") for o in ops
                 if o.get("operation") == "translate"
                 and o.get("parameters", {}).get("target") == obj_id), None)

def approx_eq(a, b, tol=1e-4):
    return abs(a - b) <= tol

def vec_eq(va, vb, tol=1e-4):
    return (len(va) == len(vb) == 3
            and all(approx_eq(a, b, tol) for a, b in zip(va, vb)))

# ── Success check ─────────────────────────────────────────────────────────────

section("SUCCESS CHECK")

obj_ids = [o.get("id") for o in objects]
all_passed = True

# --- obj_1 still present -------------------------------------------------
ok = check("obj_1 in accepted state", "obj_1" in obj_ids)
all_passed = all_passed and ok

if "obj_1" in obj_ids:
    b1 = get_box("obj_1")
    t1 = get_translate("obj_1")
    if b1:
        ok = check("obj_1 width=1.0",  approx_eq(b1.get("width",  0), 1.0),  b1.get("width"))
        all_passed = all_passed and ok
        ok = check("obj_1 height=0.05", approx_eq(b1.get("height", 0), 0.05), b1.get("height"))
        all_passed = all_passed and ok
        ok = check("obj_1 depth=0.05",  approx_eq(b1.get("depth",  0), 0.05), b1.get("depth"))
        all_passed = all_passed and ok
    if t1:
        ok = check("obj_1 offset=[0.5,0,0]", vec_eq(t1, [0.5, 0.0, 0.0]), t1)
        all_passed = all_passed and ok

# --- obj_2 present -------------------------------------------------------
ok = check("obj_2 in accepted state", "obj_2" in obj_ids)
all_passed = all_passed and ok

if "obj_2" in obj_ids:
    b2 = get_box("obj_2")
    t2 = get_translate("obj_2")
    if b2:
        ok = check("obj_2 width=0.05",  approx_eq(b2.get("width",  0), 0.05), b2.get("width"))
        all_passed = all_passed and ok
        ok = check("obj_2 height=1.0",  approx_eq(b2.get("height", 0), 1.0),  b2.get("height"))
        all_passed = all_passed and ok
        ok = check("obj_2 depth=0.05",  approx_eq(b2.get("depth",  0), 0.05), b2.get("depth"))
        all_passed = all_passed and ok
    if t2:
        ok = check("obj_2 offset=[1.0,0.5,0]", vec_eq(t2, [1.0, 0.5, 0.0]), t2)
        all_passed = all_passed and ok
    if b2 is None:
        print("[FAIL]  No create_box found for obj_2 in accepted ops")
        all_passed = False
    if t2 is None:
        print("[FAIL]  No translate found for obj_2 in accepted ops")
        all_passed = False

# --- 2 completed steps ---------------------------------------------------
ok = check("2 steps committed", len(completed_steps) == 2, len(completed_steps))
all_passed = all_passed and ok

# ── Summary ───────────────────────────────────────────────────────────────────

section("RESULT")
if all_passed:
    print("Step 1 + Step 2:  ALL CHECKS PASSED")
else:
    print("SOME CHECKS FAILED — see above for details")
