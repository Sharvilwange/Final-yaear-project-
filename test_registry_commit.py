from state.scene_registry import SceneRegistry
import json


registry = SceneRegistry(
    "scene_001",
    "Create a square"
)

candidate = {
    "schema_version": "1.0",
    "scene": {
        "name": "scene_001",
        "units": "meters"
    },
    "operations": [
        {
            "operation": "create_box",
            "parameters": {
                "id": "obj_1",
                "width": 1.0,
                "height": 0.1,
                "depth": 0.1
            }
        }
    ],
    "constraints": []
}


# -------------------------
# Test candidate
# -------------------------

registry.set_candidate(candidate)

print("\nBefore commit:")
print(json.dumps(registry.get_state(), indent=2))


# -------------------------
# Commit candidate
# -------------------------

registry.commit_candidate()

print("\nAfter commit:")
print(json.dumps(registry.get_state(), indent=2))

# -------------------------
# Test rejection
# -------------------------

bad_candidate = {
    "schema_version": "1.0",
    "scene": {
        "name": "scene_001",
        "units": "meters"
    },
    "operations": [
        {
            "operation": "create_box",
            "parameters": {
                "id": "obj_bad",
                "width": 5.0,
                "height": 5.0,
                "depth": 5.0
            }
        }
    ],
    "constraints": []
}

registry.set_candidate(bad_candidate)

registry.reject_candidate({
    "status": "invalid",
    "errors": [
        {
            "type": "incorrect_geometry",
            "message": "Candidate does not satisfy the current instruction."
        }
    ],
    "warnings": [],
    "corrections": []
})

print("\nAfter rejection:")
print(json.dumps(registry.get_state(), indent=2))