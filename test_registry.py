from state.scene_registry import SceneRegistry
import json

registry = SceneRegistry(
    "scene_001",
    "Create a square"
)

print("Initial state:")
print(json.dumps(registry.get_state(), indent=2))

registry.set_step({
    "step_id": 1,
    "instruction": "Create the first line of the square."
})

print("\nAfter planner instruction:")
print(json.dumps(registry.get_state(), indent=2))

candidate = {
    "schema_version": "1.0",
    "scene": {"name": "scene_001", "units": "meters"},
    "operations": [
        {
            "operation": "create_box",
            "parameters": {"id": "obj_1", "width": 1.0, "height": 0.05, "depth": 0.05}
        }
    ],
    "constraints": []
}

registry.set_candidate(candidate)
print("\nAfter setting candidate:")
print(json.dumps(registry.get_state(), indent=2))
assert registry.get_candidate() == candidate
assert len(registry.get_state()["operations"]) == 0  # Candidate must NOT pollute accepted operations yet!

# Test rejection on a second candidate
bad_candidate = {
    "schema_version": "1.0",
    "scene": {"name": "scene_001", "units": "meters"},
    "operations": [
        {
            "operation": "create_sphere",
            "parameters": {"id": "bad_obj", "radius": 5.0}
        }
    ],
    "constraints": []
}
registry.set_candidate(bad_candidate)
registry.reject_candidate({
    "status": "rejected",
    "errors": [{"type": "wrong_shape", "message": "Expected line/box, got sphere"}],
    "warnings": [],
    "corrections": []
})
print("\nAfter rejecting candidate:")
print(json.dumps(registry.get_state(), indent=2))
assert registry.get_candidate() is None
assert len(registry.get_state()["operations"]) == 0  # Accepted operations still empty!

# Test commitment on valid candidate
registry.set_candidate(candidate)
registry.commit_candidate()
print("\nAfter committing valid candidate:")
print(json.dumps(registry.get_state(), indent=2))
assert registry.get_candidate() is None
assert len(registry.get_state()["operations"]) == 1
assert registry.get_state()["operations"][0]["operation"] == "create_box"
assert len(registry.get_state()["objects"]) == 1
assert registry.get_state()["objects"][0]["id"] == "obj_1"

print("\nRegistry candidate state test passed successfully!")