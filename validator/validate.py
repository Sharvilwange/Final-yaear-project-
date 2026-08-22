import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

# Ensure validator directory is in sys.path for relative imports
VALIDATOR_DIR = Path(__file__).resolve().parent
if str(VALIDATOR_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATOR_DIR))

from semantic import semantic_validate

ROOT = VALIDATOR_DIR.parent
SCHEMA_PATH = ROOT / "schema" / "procedural_schema.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def validate_scene(scene_path):
    # 1. Load canonical JSON schema
    try:
        schema = load_json(SCHEMA_PATH)
    except FileNotFoundError:
        print(f"Error: Canonical schema file not found at '{SCHEMA_PATH}'")
        return False
    except json.JSONDecodeError as e:
        print(f"Error parsing schema JSON: {e}")
        return False

    # 2. Load target scene JSON
    try:
        scene = load_json(scene_path)
    except FileNotFoundError:
        print(f"Error: Scene file not found at '{scene_path}'")
        return False
    except json.JSONDecodeError as e:
        print("================================")
        print("SCENE INVALID (JSON Syntax Error)")
        print("================================")
        print(f"Error parsing scene JSON: {e}")
        return False

    # 3. JSON Schema Draft 2020-12 Validation
    validator = Draft202012Validator(schema)
    schema_errors = sorted(
        validator.iter_errors(scene),
        key=lambda error: list(error.path)
    )

    if schema_errors:
        print("================================")
        print("SCENE INVALID (Schema Errors)")
        print("================================")
        for error in schema_errors:
            path = " -> ".join(str(x) for x in error.path) if error.path else "root"
            print(f"Path: {path}")
            print(f"Error: {error.message}")
            print()
        return False

    # 4. Semantic Validation Layer
    semantic_errors = semantic_validate(scene)
    if semantic_errors:
        print("================================")
        print("SEMANTIC VALIDATION FAILED")
        print("================================")
        for error in semantic_errors:
            print(f"- {error}")
        print()
        return False

    # 5. Success
    print("================================")
    print("SCENE VALID")
    print("================================")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "python validator/validate.py <path_to_scene.json>"
        )
        sys.exit(1)

    scene_path = Path(sys.argv[1])
    if not scene_path.is_absolute():
        scene_path = ROOT / scene_path

    result = validate_scene(scene_path)
    sys.exit(0 if result else 1)
