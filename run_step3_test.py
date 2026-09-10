"""
run_step3_test.py  --  Step 3 diagnostic for 'create a square'.
Runs construction loop max_steps=3, max_retries=3.
"""
import json, sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import core.construction_loop as cl
cl.MAX_RETRIES = 3

from core.construction_loop import run_construction_loop

def section(t): print("\n" + "=" * 60 + "\n" + t + "\n" + "=" * 60)

def check(label, ok, got=None):
    s = "[PASS]" if ok else "[FAIL]"
    msg = f"{s}  {label}"
    if not ok and got is not None: msg += f"  (got: {got})"
    print(msg)
    return ok

def approx(a, b, tol=1e-4): return abs(a - b) <= tol
def vec_eq(va, vb, tol=1e-4):
    return len(va)==len(vb)==3 and all(approx(a,b,tol) for a,b in zip(va,vb))

section("END-TO-END TEST: 'create a square'  max_steps=3  max_retries=3")

final = run_construction_loop("create a square", max_steps=3, scene_id="test_step3")

objects  = final.get("objects", [])
ops      = final.get("operations", [])
steps    = final.get("completed_steps", [])
obj_ids  = [o["id"] for o in objects]

def box(oid):
    return next((o["parameters"] for o in ops
                 if o.get("operation")=="create_box" and o.get("parameters",{}).get("id")==oid), None)
def offset(oid):
    return next((o["parameters"].get("offset") for o in ops
                 if o.get("operation")=="translate" and o.get("parameters",{}).get("target")==oid), None)

section("FINAL STATE")
print(json.dumps({
    "status": final.get("status"), "stage": final.get("stage"),
    "objects": objects, "completed_steps": steps,
    "total_operations": len(ops), "operations": ops
}, indent=2))

section("SUCCESS CHECK")
all_ok = True

# obj_1
all_ok &= check("obj_1 in accepted state", "obj_1" in obj_ids)
if "obj_1" in obj_ids:
    b = box("obj_1"); t = offset("obj_1")
    if b:
        all_ok &= check("obj_1 width=1.0",  approx(b.get("width",0),  1.0),  b.get("width"))
        all_ok &= check("obj_1 height=0.05", approx(b.get("height",0), 0.05), b.get("height"))
        all_ok &= check("obj_1 depth=0.05",  approx(b.get("depth",0),  0.05), b.get("depth"))
    if t: all_ok &= check("obj_1 offset=[0.5,0,0]", vec_eq(t,[0.5,0.0,0.0]), t)

# obj_2
all_ok &= check("obj_2 in accepted state", "obj_2" in obj_ids)
if "obj_2" in obj_ids:
    b = box("obj_2"); t = offset("obj_2")
    if b:
        all_ok &= check("obj_2 width=0.05",  approx(b.get("width",0),  0.05), b.get("width"))
        all_ok &= check("obj_2 height=1.0",  approx(b.get("height",0), 1.0),  b.get("height"))
        all_ok &= check("obj_2 depth=0.05",  approx(b.get("depth",0),  0.05), b.get("depth"))
    if t: all_ok &= check("obj_2 offset=[1.0,0.5,0]", vec_eq(t,[1.0,0.5,0.0]), t)

# obj_3 — top edge
all_ok &= check("obj_3 in accepted state", "obj_3" in obj_ids)
if "obj_3" in obj_ids:
    b = box("obj_3"); t = offset("obj_3")
    if b:
        all_ok &= check("obj_3 width=1.0",   approx(b.get("width",0),  1.0),  b.get("width"))
        all_ok &= check("obj_3 height=0.05",  approx(b.get("height",0), 0.05), b.get("height"))
        all_ok &= check("obj_3 depth=0.05",   approx(b.get("depth",0),  0.05), b.get("depth"))
    else:
        print("[FAIL]  No create_box found for obj_3"); all_ok = False
    if t:
        all_ok &= check("obj_3 offset=[0.5,1.0,0]", vec_eq(t,[0.5,1.0,0.0]), t)
    else:
        print("[FAIL]  No translate found for obj_3"); all_ok = False
else:
    print("[FAIL]  obj_3 missing — Step 3 did not commit")

all_ok &= check("3 steps committed", len(steps)==3, len(steps))

# Duplicate-op guard: obj_3 must appear exactly once in create_box ops
obj3_count = sum(1 for o in ops
                 if o.get("operation")=="create_box"
                 and o.get("parameters",{}).get("id")=="obj_3")
all_ok &= check("obj_3 created exactly once (no duplicate accumulation)",
                obj3_count == 1, obj3_count)

section("RESULT")
if all_ok:
    print("Steps 1 + 2 + 3:  ALL CHECKS PASSED")
else:
    print("SOME CHECKS FAILED -- see above for details")
    print("\nPartial state for diagnosis:")
    print(f"  obj_ids in registry   : {obj_ids}")
    print(f"  completed_steps count : {len(steps)}")
    print(f"  total operations      : {len(ops)}")
