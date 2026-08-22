import json
import ollama
import sys
from pathlib import Path
from jsonschema import validate

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from builder.qwen_builder import build_scene

def run_llm_validator(user_prompt,scene_plan, builder_output):

    response = ollama.chat(
        model="deepseek-r1:7b",
        format="json",
        messages=[
            {
                "role": "system",
                "content": """
You are the validation stage of an AI procedural 3D system.

Your job is to inspect the user's request and the generated
Builder output.

Determine whether the Builder output correctly represents
the user's request.

Check for:
- missing objects
- unnecessary objects
- incorrect object types
- incorrect dimensions
- incorrect relationships
- incorrect constraints
- missing required operations
- contradictory operations
- obvious procedural 3D mistakes

Do NOT generate Blender code.
Do NOT modify the Builder output.
Do NOT generate new operations.

Return ONLY valid JSON following this structure:

{
  "valid": true,
  "errors": [],
  "warnings": [],
  "corrections": []
}

Every error or warning MUST contain:
- "type"
- "message"

"objects" may optionally contain relevant object IDs.

Every correction MUST contain:
- "target"
- "action"
- "reason"
"""
            },
            {
                "role": "user",
                "content": json.dumps({
                    "user_request": user_prompt,
                     "scene_plan": scene_plan,
                    "builder_output": builder_output
                }, indent=2)
            }
        ]
    )

    raw_response = response["message"]["content"].strip()

    if raw_response.startswith("```"):
        raw_response = raw_response.replace("```json", "", 1)
        raw_response = raw_response.replace("```", "", 1)
        raw_response = raw_response.strip()
        print("\n--- RAW VALIDATOR RESPONSE ---")
        print(raw_response)
        print("--- END RAW VALIDATOR RESPONSE ---")

    return json.loads(raw_response)

def validate_llm_result(validation_result):
    validate(
        instance=validation_result,
        schema=validator_schema
    )

    return True
BASE_DIR = Path(__file__).resolve().parent.parent

VALIDATOR_SCHEMA_PATH = BASE_DIR / "schema" / "validator_schema.json"

with open(VALIDATOR_SCHEMA_PATH, "r", encoding="utf-8") as f:
    validator_schema = json.load(f)

BUILDER_SCHEMA_PATH = BASE_DIR / "schema" / "builder_schema.json"

with open(BUILDER_SCHEMA_PATH, "r", encoding="utf-8") as f:
    builder_schema = json.load(f)    

def validate_builder_output(builder_output):
    validate(
        instance=builder_output,
        schema=builder_schema
    )

    return True

print("Validator schema loaded successfully.")

# --------------------------------
# Standalone Builder test
# --------------------------------
if __name__ == "__main__":

    user_prompt = input("Enter your 3D scene request: ")

    scene_plan , builder_output = build_scene(user_prompt)

    validate_builder_output(builder_output)

    validation_result = run_llm_validator(
        user_prompt,
        scene_plan,
        builder_output
    )

    validate_llm_result(validation_result)

    print("\nValidator output is valid.")
    print(json.dumps(validation_result, indent=2))