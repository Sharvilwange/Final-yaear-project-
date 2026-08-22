import ollama
import json 
from pathlib import Path
from jsonschema import validate



BASE_DIR = Path(__file__).resolve().parent.parent
PLANNER_SCHEMA_PATH = BASE_DIR / "schema" / "planner.json"
with open(PLANNER_SCHEMA_PATH, "r", encoding="utf-8") as f:
    planner_schema = json.load(f)


def generate_scene_plan(user_prompt):

    response = ollama.chat(
    model="deepseek-r1:7b",
    format=planner_schema,
    messages=[
        {
            "role": "system",
            "content": """
You are the planning stage of an AI procedural 3D system.

Your job is ONLY to create a structured scene plan.

You must return ONLY valid JSON.
Do not use Markdown.
Do not use ```json.
Do not include explanations.
Do not include reasoning outside the JSON.

The JSON MUST follow this exact structure:

{
  "scene": {
    "name": "string",
    "description": "string"
  },
  "objects": [
    {
      "id": "obj_1",
      "type": "string",
      "description": "string",
      "dimensions": {
        "width": 0,
        "height": 0,
        "depth": 0,
        "radius": 0
      }
    }
  ],
  "relationships": [
    {
      "type": "string",
      "objects": ["obj_1", "obj_2"],
      "description": "string"
    }
  ],
  IMPORTANT DIMENSIONS RULE:

The "dimensions" object is the ONLY place where dimensions
may appear.

If an object has dimensions, they MUST be written like:

"dimensions": {
  "width": 0.8,
  "height": 0.45,
  "depth": 0.4
}

NEVER put "width", "height", "depth", or "radius" outside
the "dimensions" object.

The object itself may contain only:
- id
- type
- description
- dimensions
  "constraints": [
    {
      "type": "string",
      "description": "string"
    }
  ]
}

IMPORTANT CONSTRAINT FORMAT:
Every item in "constraints" MUST be a JSON object.

Correct:
{
  "type": "symmetry",
  "objects": ["obj_1", "obj_2"],
  "description": "The legs are evenly distributed."
}

Incorrect:
"The legs are evenly distributed."

Never return a constraint as a plain string.

- Every constraint MUST contain "type" and "description".
- If a constraint applies to specific objects, include "objects".

Rules:
- Object IDs must be obj_1, obj_2, obj_3, etc.
- Do NOT generate operations such as create_box, translate, rotate, scale, duplicate, etc.
- Do NOT generate Blender code.
- Do NOT generate operation IDs such as op_1.
- Describe what should exist and how objects relate to each other.
- Every relationship MUST contain at least two object IDs.
- Never create a relationship with only one object.
- Only include dimension fields that are meaningful for the object.
- For box-like objects use width, height, and depth.
- For circular objects use radius when applicable.
- Never use null for any dimension.
- If a dimension is not applicable or unknown, omit that field.
"""
        },
        {
            "role": "user",
            "content": user_prompt
        }
    ]
)
    scene_plan_text = response["message"]["content"].strip()

    if scene_plan_text.startswith("```"):
        scene_plan_text = scene_plan_text.replace("```json", "", 1)
        scene_plan_text = scene_plan_text.replace("```", "", 1)
        scene_plan_text = scene_plan_text.strip()
        
    print("\n--- PLANNER RAW OUTPUT ---")
    print(scene_plan_text)
    print("--- END PLANNER RAW OUTPUT ---") 
    try:
        scene_plan = json.loads(scene_plan_text)
    except json.JSONDecodeError as e:
        print("\n--- INVALID PLANNER JSON ---")
        print(scene_plan_text)
        print("--- END INVALID JSON ---")
        print(f"JSON error: {e}")
        raise 

    validate(instance=scene_plan, schema=planner_schema)

    return scene_plan
