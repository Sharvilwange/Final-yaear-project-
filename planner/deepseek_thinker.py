"""
Planner module — DeepSeek R1 7B Step Planner.

generate_next_instruction()  → State-aware next step generation
generate_scene_plan()        → Legacy full-scene plan (kept as fallback)
"""

import ollama
import json
import re
import sys
from pathlib import Path
from jsonschema import validate

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from state.scene_registry import SceneRegistry
from config import PLANNER_MODEL

PLANNER_SCHEMA_PATH = BASE_DIR / "schema" / "planner.json"
with open(PLANNER_SCHEMA_PATH, "r", encoding="utf-8") as f:
    planner_schema = json.load(f)

STEP_SCHEMA_PATH = BASE_DIR / "schema" / "step_instruction.json"
with open(STEP_SCHEMA_PATH, "r", encoding="utf-8") as f:
    step_instruction_schema = json.load(f)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _strip_think_tags(text: str) -> str:
    """
    Remove DeepSeek-R1 <think>...</think> reasoning blocks.
    These appear before the actual JSON output and must be stripped
    before any JSON parsing attempt.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_json_object(raw_text):
    """
    Extract the first JSON object from an LLM response.
    Handles plain JSON, explanatory text, and ```json fences.
    """
    raw_text = raw_text.strip()

    if "```json" in raw_text:
        raw_text = raw_text.split("```json", 1)[1]

    if "```" in raw_text:
        raw_text = raw_text.split("```", 1)[0]

    raw_text = raw_text.strip()

    start = raw_text.find("{")
    end   = raw_text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            f"No JSON object found in Planner response: {raw_text!r}"
        )

    return json.loads(raw_text[start:end + 1])


def _extract_object_positions(operations: list) -> dict:
    """
    Extract object spatial data (center, dimensions, bounds) from committed
    operations so the Planner can use exact coordinates for subsequent steps.
    """
    objects = {}

    for op in operations:
        op_name = op.get("operation", "")
        params  = op.get("parameters", {})

        if op_name == "create_box" and "id" in params:
            obj_id = params["id"]
            objects[obj_id] = {
                "width":  float(params.get("width",  1.0)),
                "height": float(params.get("height", 1.0)),
                "depth":  float(params.get("depth",  1.0)),
                "center": [0.0, 0.0, 0.0],
            }
        elif op_name == "translate" and "target" in params:
            target = params["target"]
            if target in objects:
                objects[target]["center"] = [float(v) for v in params.get("offset", [0, 0, 0])]

    # Compute extremes for each object
    result = {}
    for obj_id, obj in objects.items():
        cx, cy, cz = obj["center"]
        hw = obj["width"]  / 2
        hh = obj["height"] / 2
        hd = obj["depth"]  / 2
        result[obj_id] = {
            "center": [round(cx, 4), round(cy, 4), round(cz, 4)],
            "width":  obj["width"],
            "height": obj["height"],
            "depth":  obj["depth"],
            "x_range": [round(cx - hw, 4), round(cx + hw, 4)],
            "y_range": [round(cy - hh, 4), round(cy + hh, 4)],
            "z_range": [round(cz - hd, 4), round(cz + hd, 4)],
        }

    return result


# ------------------------------------------------------------------
# State-aware step planner
# ------------------------------------------------------------------

def generate_next_instruction(user_prompt: str, accepted_state: dict) -> dict:
    """
    Generate the NEXT small construction step based on the current accepted state.

    Parameters:
        user_prompt:    Original user goal.
        accepted_state: Clean accepted state from registry.get_accepted_state().

    Returns:
        Step instruction dict conforming to step_instruction.json schema.
    """

    completed_steps    = accepted_state.get("completed_steps", [])
    objects_built      = accepted_state.get("objects", [])
    operations_count   = len(accepted_state.get("operations", []))
    object_positions   = _extract_object_positions(accepted_state.get("operations", []))

    next_step_id = len(completed_steps) + 1

    # Build progress summary
    if completed_steps:
        progress_summary = f"Steps completed so far ({len(completed_steps)} total):\n"
        for cs in completed_steps:
            progress_summary += (
                f"  - Step {cs.get('step_id')}: {cs.get('instruction', 'unknown')} "
                f"[target: {cs.get('target', '?')}]\n"
            )
    else:
        progress_summary = "No steps have been completed yet. This is the FIRST step."

    if objects_built:
        objects_summary = "Objects already in the scene:\n"
        for obj in objects_built:
            obj_id = obj.get("id")
            objects_summary += f"  - {obj_id}: {obj.get('type')}"
            if obj_id in object_positions:
                pos = object_positions[obj_id]
                objects_summary += (
                    f" | center={pos['center']} | "
                    f"x=[{pos['x_range'][0]},{pos['x_range'][1]}] "
                    f"y=[{pos['y_range'][0]},{pos['y_range'][1]}] "
                    f"z=[{pos['z_range'][0]},{pos['z_range'][1]}]"
                )
            objects_summary += "\n"
    else:
        objects_summary = "No objects have been built yet."

    system_prompt = f"""
You are the Step Planner in an AI procedural 3D construction system.

Your job is to decide ONLY the NEXT single small construction step.

IMPORTANT RULES:
1. Return ONLY valid JSON. No markdown. No explanation.
2. Give exactly ONE construction instruction for the next step.
3. Do NOT recreate objects that already exist in the scene.
4. Do NOT describe the entire remaining scene.
5. Focus only on the next required step to progress toward the goal.
6. The "target" field MUST contain only the object ID (e.g., "obj_1").
7. If the goal is FULLY COMPLETE (all required parts exist), set "is_complete" to true.
8. "requirements" MUST be a JSON object — NEVER an array.

PROGRESS TRACKING:
{progress_summary}

{objects_summary}

The next step MUST be step_id = {next_step_id}.
Do NOT use any other step_id.

====== REQUIREMENTS FORMAT ======

For geometric primitives, the "requirements" field MUST include:

For a LINE / EDGE / SIDE:
{{
  "primitive": "line",
  "length": <float, metres>,
  "start":  [x, y, z],
  "direction": [dx, dy, dz],
  "thickness": 0.05
}}

IMPORTANT:
- Always provide explicit "start" coordinates.
- Derive "start" from the object_positions of already-built objects.
- Use "direction" = [1,0,0] for horizontal X, [0,1,0] for vertical Y, [0,0,1] for Z.
- "thickness" should be 0.05 (thin line representation).

====== COORDINATE EXAMPLES ======

====== COORDINATE EXAMPLES ======

For "Create a 1 metre square" in the XY plane (z=0):

Step 1 — bottom edge:
start = [0,0,0]
direction = [1,0,0]
length = 1.0
target = obj_1

Step 2 — right edge:
start = [1,0,0]
direction = [0,1,0]
length = 1.0
target = obj_2

Step 3 — top edge:
start = [1,1,0]
direction = [-1,0,0]
length = 1.0
target = obj_3

Step 4 — left edge:
start = [0,1,0]
direction = [0,-1,0]
length = 1.0
target = obj_4

The direction vector describes the direction FROM start TO end.

The endpoint is:

end = start + direction * length

Therefore:

Step 1 endpoint = [1,0,0]
Step 2 endpoint = [1,1,0]
Step 3 endpoint = [0,1,0]
Step 4 endpoint = [0,0,0]

All four edges must connect sequentially and form one closed square.

Always look at the existing object x_range / y_range to find the correct
start for the next edge.

====== OUTPUT FORMAT ======

You MUST return exactly ONE JSON object matching the required schema.
Do not create alternate keys such as line, geometry, start_point, end_point, or coordinates.
For line requirements use ONLY: primitive, length, start, direction, thickness.
The target object ID must remain in: target
The geometry must remain inside: requirements

{{
  "step_id": {next_step_id},
  "instruction": "Create the first line of the square (bottom edge).",
  "target": "obj_1",
  "requirements": {{
    "primitive": "line",
    "length": 1.0,
    "start": [0, 0, 0],
    "direction": [1, 0, 0],
    "thickness": 0.05
  }},
  "is_complete": false
}}

Set "is_complete": true ONLY when ALL required parts of the goal are built.
Think carefully about what has already been built before deciding the next step.
"""

    user_content = json.dumps({
        "user_goal":              user_prompt,
        "next_step_id":           next_step_id,
        "accepted_objects":       objects_built,
        "object_positions":       object_positions,
        "completed_steps":        completed_steps,
        "total_operations_committed": operations_count,
    }, indent=2)

    response = ollama.chat(
        model=PLANNER_MODEL,
        format="json",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content}
        ]
    )

    raw_output = response["message"]["content"]
    # Strip DeepSeek-R1 <think>...</think> reasoning preamble first
    raw_output = _strip_think_tags(raw_output)
    raw_output = _strip_fences(raw_output)

    try:
        step_instruction = json.loads(raw_output)
    except json.JSONDecodeError as e:
        # Fallback: try to extract the first JSON object from the raw text
        print(f"[Planner Warning] Direct json.loads failed ({e}), trying extract_json_object...")
        try:
            step_instruction = extract_json_object(raw_output)
        except Exception as e2:
            print(f"\n[Planner Error] Failed to parse step instruction JSON: {e2}")
            print(f"[Planner Error] Raw output: {raw_output!r}")
            raise ValueError(
                f"Planner could not parse JSON from DeepSeek output: {e2}"
            ) from e2

    # Enforce authoritative step_id from registry (don't trust LLM step_id)
    step_instruction["step_id"] = next_step_id
    
    # Enforce authoritative target to prevent the LLM from reusing previous object IDs
    step_instruction["target"] = f"obj_{next_step_id}"

    # Ensure is_complete exists
    if "is_complete" not in step_instruction:
        step_instruction["is_complete"] = False

    # Guard: requirements MUST be a dict, not a list
    reqs = step_instruction.get("requirements")
    if isinstance(reqs, list):
        print("[Planner Warning] requirements returned as array — converting to object.")
        merged = {}
        for item in reqs:
            if isinstance(item, dict):
                merged.update(item)
        step_instruction["requirements"] = merged
    elif reqs is None:
        step_instruction["requirements"] = {}

    # Validate against schema
       # Validate against the dedicated step-instruction schema.
    #
    # IMPORTANT:
    # A malformed Planner response must NEVER be converted into a fake
    # "Continue building the scene." instruction. That can cause the
    # Builder and Validator to operate on invalid state.
    try:
        validate(
            instance=step_instruction,
            schema=step_instruction_schema
        )
    except Exception as schema_err:
        print(
            f"[Planner Error] Step instruction failed schema validation:\n"
            f"{schema_err}"
        )
        print(
            "[Planner Error] Invalid Planner output:\n"
            f"{json.dumps(step_instruction, indent=2)}"
        )

        raise ValueError(
            "Planner generated an invalid step instruction. "
            "The construction loop must retry Planner generation "
            "instead of using a fabricated fallback step."
        ) from schema_err

    return step_instruction


# ------------------------------------------------------------------
# Legacy full-scene planner (kept as fallback)
# ------------------------------------------------------------------

def generate_scene_plan(user_prompt: str) -> dict:
    """
    Generate a complete scene plan (legacy).
    Used by the original build_scene() flow.
    """
    response = ollama.chat(
        model=PLANNER_MODEL,
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
  "constraints": [
    {
      "type": "string",
      "description": "string"
    }
  ]
}

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

    scene_plan_text = response["message"]["content"]
    scene_plan_text = _strip_fences(scene_plan_text)

    print("\n--- PLANNER RAW OUTPUT ---")
    print(scene_plan_text)
    print("--- END PLANNER RAW OUTPUT ---")

    try:
        step_instruction = extract_json_object(scene_plan_text)
    except json.JSONDecodeError as e:
        print("\n--- INVALID PLANNER JSON ---")
        print(scene_plan_text)
        print(f"JSON error: {e}")
        raise

    return step_instruction


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------

if __name__ == "__main__":
    user_prompt = input("Enter your 3D scene request: ")

    registry = SceneRegistry("scene_001", user_prompt)

    accepted = registry.get_accepted_state()
    step = generate_next_instruction(user_prompt, accepted)

    registry.set_step(step)

    print("\nNext Planner Instruction:")
    print(json.dumps(step, indent=2))

    print("\nUpdated Scene Registry:")
    print(json.dumps(registry.get_state(), indent=2))