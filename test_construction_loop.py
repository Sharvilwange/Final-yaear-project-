import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve()
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from state.scene_registry import SceneRegistry
from validator.qwen_validator import validate_candidate, validate_llm_result
from core.construction_loop import run_construction_loop

def test_candidate_state_isolation():
    registry = SceneRegistry("scene_test", "Create a cube")
    
    # 1. Verify candidate is initially None
    assert registry.get_candidate() is None
    assert len(registry.get_state()["operations"]) == 0
    
    # 2. Set candidate
    cand = {
        "schema_version": "1.0",
        "scene": {"name": "scene_test", "units": "meters"},
        "operations": [{"operation": "create_box", "parameters": {"id": "obj_1", "width": 1, "height": 1, "depth": 1}}],
        "constraints": []
    }
    registry.set_candidate(cand)
    assert registry.get_candidate() == cand
    assert len(registry.get_state()["operations"]) == 0, "Candidate must NOT be in accepted operations"

    # 3. Reject candidate -> must clear candidate, accepted ops remain empty
    registry.reject_candidate({"valid": False, "errors": [{"type": "error", "message": "Failed test"}], "warnings": [], "corrections": []})
    assert registry.get_candidate() is None
    assert len(registry.get_state()["operations"]) == 0, "Rejected candidate must not pollute accepted state"

    # 4. Commit candidate -> candidate ops become accepted ops
    registry.set_candidate(cand)
    registry.commit_candidate()
    assert registry.get_candidate() is None
    assert len(registry.get_state()["operations"]) == 1
    assert registry.get_state()["operations"][0]["operation"] == "create_box"

    print("[PASS] test_candidate_state_isolation")

def test_validator_interface():
    step_instruction = {
        "step_id": 1,
        "instruction": "Create the first side of a box",
        "target": "obj_1"
    }
    scene_state = {
        "objects": [],
        "operations": []
    }
    builder_output = {
        "schema_version": "1.0",
        "scene": {"name": "scene_001", "units": "meters"},
        "operations": [{"operation": "create_box", "parameters": {"id": "obj_1", "width": 1, "height": 1, "depth": 1}}],
        "constraints": []
    }

    result = validate_candidate(
        user_prompt="Create a cube",
        planner_instruction=step_instruction,
        scene_state=scene_state,
        builder_output=builder_output
    )

    # Must conform to validator schema
    assert validate_llm_result(result)
    assert "valid" in result
    assert "errors" in result
    assert "warnings" in result
    assert "corrections" in result
    print("[PASS] test_validator_interface")

if __name__ == "__main__":
    print("Running construction loop tests...")
    test_candidate_state_isolation()
    test_validator_interface()
    print("All unit tests passed successfully!")
