"""
run_step1_test.py — Full end-to-end test for Step 1 of 'create a square'.
Runs the construction loop with max_steps=1, max_retries=3.
Prints verbose output of each stage.
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Patch MAX_RETRIES in construction_loop before importing
import core.construction_loop as cl
cl.MAX_RETRIES = 3

from core.construction_loop import run_construction_loop

print("=" * 60)
print("END-TO-END TEST: 'create a square' max_steps=1 max_retries=3")
print("=" * 60)

final_state = run_construction_loop(
    user_prompt="create a square",
    max_steps=1,
    scene_id="test_step1",
)

print("\n" + "=" * 60)
print("FINAL STATE SUMMARY")
print("=" * 60)
accepted = final_state.get("accepted_state") or {
    "objects":          final_state.get("objects", []),
    "operations":       final_state.get("operations", []),
    "completed_steps":  final_state.get("completed_steps", []),
}

summary = {
    "status":           final_state.get("status"),
    "stage":            final_state.get("stage"),
    "objects":          final_state.get("objects", []),
    "completed_steps":  final_state.get("completed_steps", []),
    "total_operations": len(final_state.get("operations", [])),
    "operations":       final_state.get("operations", []),
}
print(json.dumps(summary, indent=2))

# Success check
objects = final_state.get("objects", [])
ops     = final_state.get("operations", [])
obj_ids = [o.get("id") for o in objects]

print("\n" + "=" * 60)
print("SUCCESS CHECK")
print("=" * 60)
if "obj_1" in obj_ids:
    print("[OK] obj_1 committed to accepted state")
    # Find create_box for obj_1
    box_op = next((o for o in ops if o.get("operation") == "create_box"
                   and o.get("parameters", {}).get("id") == "obj_1"), None)
    tr_op  = next((o for o in ops if o.get("operation") == "translate"
                   and o.get("parameters", {}).get("target") == "obj_1"), None)
    if box_op:
        p = box_op["parameters"]
        print(f"  create_box: width={p.get('width')} height={p.get('height')} depth={p.get('depth')}")
        ok = (p.get("width") == 1.0 and p.get("height") == 0.05 and p.get("depth") == 0.05)
        print(f"  Dimensions correct (w=1.0 h=0.05 d=0.05): {ok}")
    if tr_op:
        off = tr_op["parameters"].get("offset", [])
        print(f"  translate offset: {off}")
        ok = (len(off) == 3 and abs(off[0] - 0.5) < 1e-6 and abs(off[1]) < 1e-6 and abs(off[2]) < 1e-6)
        print(f"  Offset correct ([0.5, 0.0, 0.0]): {ok}")
    if not box_op:
        print("  WARNING: No create_box operation found for obj_1")
    if not tr_op:
        print("  WARNING: No translate operation found for obj_1")
else:
    print(f"[FAIL] obj_1 NOT in accepted state. Objects: {obj_ids}")
    print("  STEP 1 FAILED")
