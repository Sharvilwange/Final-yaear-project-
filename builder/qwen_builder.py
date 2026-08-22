import ollama
import json
import sys
from pathlib import Path
from jsonschema import validate

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


from planner.deepseek_thinker import generate_scene_plan


OPERATIONS_PATH = BASE_DIR / "schema" / "operations.json"

with open(OPERATIONS_PATH, "r", encoding="utf-8") as f:
    operations_schema = json.load(f)


BUILDER_SCHEMA_PATH = BASE_DIR / "schema" / "builder_schema.json"

with open(BUILDER_SCHEMA_PATH, "r", encoding="utf-8") as f:
    builder_schema = json.load(f)


def build_scene(user_prompt):

    # -----------------------------
    # 1. Generate scene plan
    # -----------------------------

    scene_plan = generate_scene_plan(user_prompt)

    # -----------------------------
    # 2. Qwen 2.5 Builder
    # -----------------------------

    response = ollama.chat(
        model="qwen2.5:latest",
        format="json",
        messages=[
            {
                "role": "system",
                "content": """
You are the Builder model in an AI procedural 3D system.

Your job is to convert the provided scene plan into a structured
3D construction representation.

Use ONLY the operations provided in the AVAILABLE OPERATIONS section.

Do not invent operations.
Do not generate Blender code.
Do not explain your answer.
Return ONLY valid JSON.
Do not use Markdown or ```json fences.

The output MUST have exactly these top-level fields:

{
  "schema_version": "1.0",
  "scene": {
    "name": "scene name",
    "units": "meters"
  },
  "operations": [],
  "constraints": []
}

IMPORTANT:

The "parameters" field MUST ALWAYS be a JSON object.

NEVER use an array for "parameters".

Use parameter names exactly as defined by the available operations.

Do not add parameters.
Do not remove required parameters.
Do not change parameter names.

Example:

{
  "operation": "create_box",
  "parameters": {
    "id": "obj_1",
    "width": 2,
    "height": 1,
    "depth": 1
  }
}

Example:

{
  "operation": "translate",
  "parameters": {
    "target": "obj_1",
    "offset": [0, 1, 0]
  }
}

Each item in "operations" MUST contain:

- "operation"
- "parameters"

The operation name MUST exactly match one of the
available operations.

--------------------------------
CONSTRAINT RULE
--------------------------------

A constraint may contain ONLY:

- "type"
- "objects"
- "parameters"

Constraint-specific values MUST go inside "parameters".

Example:

{
  "type": "symmetry",
  "objects": ["obj_1", "obj_2"],
  "parameters": {
    "axis": "x"
  }
}

NEVER put "axis", "distance", or other constraint-specific
fields directly inside the constraint object.

Even if there are no constraints:

"constraints": []

--------------------------------
OPERATION / CONSTRAINT SEPARATION
--------------------------------

Operations and constraints are completely different.

ALL actions that create or modify geometry MUST go inside
the "operations" array.

Examples:

- create_box
- create_sphere
- create_cylinder
- create_cone
- create_plane
- create_torus
- translate
- rotate
- scale
- duplicate
- repeat
- mirror
- group
- combine
- extrude

These MUST NEVER appear inside "constraints".

The "constraints" array is ONLY for relationships or
geometric requirements.

Examples:

- symmetry
- alignment
- distance
- support
- same_size

A constraint MUST contain:

- "type"
- "objects"

and MAY contain:

- "parameters"

--------------------------------
TOP LEVEL REQUIREMENTS
--------------------------------

The response MUST contain exactly:

- "schema_version"
- "scene"
- "operations"
- "constraints"

"schema_version" MUST be:

"1.0"

"scene" MUST contain:

- "name"
- "units"

"units" MUST be one of:

- "meters"
- "centimeters"
- "millimeters"

"operations" MUST be an array.

"constraints" MUST be an array.

--------------------------------
AVAILABLE OPERATIONS
--------------------------------
"""
                + json.dumps(operations_schema, indent=2)
            },
            {
                "role": "user",
                "content": json.dumps(scene_plan)
            }
        ]
    )

    # -----------------------------
    # 3. Parse Builder output
    # -----------------------------

    raw_output = response["message"]["content"].strip()

    if raw_output.startswith("```"):
        raw_output = raw_output.replace("```json", "", 1)
        raw_output = raw_output.replace("```", "", 1)
        raw_output = raw_output.strip()

    builder_output = json.loads(raw_output)

    # -----------------------------
    # 4. Validate Builder output
    # -----------------------------

    validate(
        instance=builder_output,
        schema=builder_schema
    )

    return scene_plan , builder_output


# --------------------------------
# Standalone Builder test
# --------------------------------
if __name__ == "__main__":
    user_prompt = input("Enter your 3D scene request: ")

    scene_plan ,builder_output = build_scene(user_prompt)

    print("Builder output is valid.")
    print(json.dumps(builder_output, indent=2))
