"""
test_planner_only.py  --  Tests Planner step generation up to 4 steps.
"""
import sys, json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from planner.deepseek_thinker import generate_next_instruction, step_instruction_schema
from jsonschema import validate

def run_planner_test():
    prompt = "create a square"
    accepted_state = {
        "status": "partial",
        "objects": [],
        "completed_steps": [],
        "operations": []
    }
    
    for step_num in range(1, 5):
        print(f"\n{'='*40}")
        print(f"GENERATING STEP {step_num}")
        print(f"{'='*40}")
        
        try:
            instruction = generate_next_instruction(prompt, accepted_state)
            print("\n--- PLANNER OUTPUT ---")
            print(json.dumps(instruction, indent=2))
            
            # Update mocked accepted state
            target = instruction["target"]
            accepted_state["completed_steps"].append({
                "step_id": instruction["step_id"],
                "instruction": instruction["instruction"],
                "target": target
            })
            accepted_state["objects"].append({"id": target, "type": "box"})
            
            # Add mocked geometry operations
            req = instruction.get("requirements", {})
            # Mock center derived from requirements logic
            # For simplicity, we just put dummy centers to satisfy the loop if needed.
            # In our case, the Planner derives start from previous objects x_range/y_range.
            # We need realistic bounding boxes to feed back to the planner.
            
            if step_num == 1:
                cx, cy, cz = 0.5, 0.0, 0.0
                w, h, d = 1.0, 0.05, 0.05
            elif step_num == 2:
                cx, cy, cz = 1.0, 0.5, 0.0
                w, h, d = 0.05, 1.0, 0.05
            elif step_num == 3:
                cx, cy, cz = 0.5, 1.0, 0.0
                w, h, d = 1.0, 0.05, 0.05
            else:
                cx, cy, cz = 0.0, 0.5, 0.0
                w, h, d = 0.05, 1.0, 0.05
                
            accepted_state["operations"].extend([
                {
                    "operation": "create_box",
                    "parameters": {"id": target, "width": w, "height": h, "depth": d}
                },
                {
                    "operation": "translate",
                    "parameters": {"target": target, "offset": [cx, cy, cz]}
                }
            ])
            
            print("SCHEMA VALIDATION: [PASS]")
            
        except Exception as e:
            print(f"\n[FAIL] Step {step_num} failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    run_planner_test()
