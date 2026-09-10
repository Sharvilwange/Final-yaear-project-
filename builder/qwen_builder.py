"""
Builder module — Qwen 2.5 Procedural Builder.

build_next_step()   → Builds ONE construction step (deterministic or LLM).
build_scene()       → Legacy full-scene builder (kept for backward compatibility).

Deterministic path:
    When the Planner supplies structured requirements with a recognised primitive
    (line, edge, segment, side), geometry.requirements_to_operations() computes
    the exact create_box + translate parameters in Python.
    The LLM is NOT used for geometry in this case — eliminating creative drift.

LLM fallback:
    For unrecognised primitives or complex geometry, Qwen 2.5 generates the ops
    using the existing prompt structure.  validator feedback is injected at the
    top of the system prompt on retry attempts.
"""

import ollama
import json
import sys
from pathlib import Path
from jsonschema import validate

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import BUILDER_MODEL
from geometry import requirements_to_operations

# ------------------------------------------------------------------
# Schema loading
# ------------------------------------------------------------------

BUILDER_SCHEMA_PATH = BASE_DIR / "schema" / "builder_schema.json"
with open(BUILDER_SCHEMA_PATH, "r", encoding="utf-8") as f:
    builder_schema = json.load(f)

OPERATIONS_SCHEMA_PATH = BASE_DIR / "schema" / "operations.json"
with open(OPERATIONS_SCHEMA_PATH, "r", encoding="utf-8") as f:
    operations_schema = json.load(f)

# ------------------------------------------------------------------
# Allowed operations (gate against hallucinated op names)
# ------------------------------------------------------------------

ALLOWED_OPERATIONS = {
    "create_box",
    "create_sphere",
    "create_cylinder",
    "create_cone",
    "create_torus",
    "translate",
    "rotate",
    "scale",
    "duplicate",
    "boolean_union",
    "boolean_difference",
    "boolean_intersection",
}


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


# ------------------------------------------------------------------
# Main builder function
# ------------------------------------------------------------------

def build_next_step(
    step_instruction: dict,
    accepted_state: dict,
    registry=None,
    validation_feedback=None
) -> dict:
    """
    Build ONE small construction step as specified by the Planner instruction.

    Parameters:
        step_instruction:   Current Planner step instruction (incl. requirements).
        accepted_state:     Clean accepted state from registry.get_accepted_state().
        registry:           Optional SceneRegistry (unused here; set by loop).
        validation_feedback: Validator result from the previous attempt, or None.

    Returns:
        Builder output dict conforming to builder_schema.json.
    """

    existing_objects   = accepted_state.get("objects", [])
    existing_ops_count = len(accepted_state.get("operations", []))
    target_id          = step_instruction.get("target", "obj_1")
    requirements       = step_instruction.get("requirements") or {}

    # ── DETERMINISTIC PATH ─────────────────────────────────────────────────
    # When requirements describe a known geometric primitive, compute exact
    # create_box + translate parameters in Python — do NOT use LLM for geometry.

    det_ops = requirements_to_operations(target_id, requirements)

    if det_ops is not None:
        primitive = requirements.get("primitive", "?")
        print(f"[BUILDER] Deterministic geometry for primitive='{primitive}' — skipping LLM.")

        builder_output = {
            "schema_version": "1.0",
            "scene": {"name": "scene", "units": "meters"},
            "operations": det_ops,
            "constraints": [],
        }

        try:
            validate(instance=builder_output, schema=builder_schema)
            bad_ops = [
                op.get("operation") for op in det_ops
                if op.get("operation") not in ALLOWED_OPERATIONS
            ]
            if bad_ops:
                raise ValueError(f"Deterministic ops contain disallowed operations: {bad_ops}")

            print(f"[BUILDER] Deterministic candidate: {len(det_ops)} operations")
            return builder_output

        except Exception as det_err:
            print(f"[BUILDER Warning] Deterministic path error: {det_err} — falling back to LLM.")
            # Fall through to LLM path below

    # ── LLM PATH ───────────────────────────────────────────────────────────

    # Build context for existing objects
    if existing_objects:
        existing_summary = "Objects already in the accepted scene (DO NOT recreate these):\n"
        for obj in existing_objects:
            existing_summary += f"  - {obj.get('id')}: type={obj.get('type')}\n"
    else:
        existing_summary = "No objects exist yet. This is the first construction step."

    # ------------------------------------------------------------------
    # Build feedback text BEFORE the system prompt so it is injected first
    # ------------------------------------------------------------------
    if validation_feedback:
        errors_text      = json.dumps(validation_feedback.get("errors",      []), indent=2)
        corrections_text = json.dumps(validation_feedback.get("corrections", []), indent=2)
        feedback_text = f"""
PREVIOUS VALIDATOR FEEDBACK — you MUST address every item below:

The previous candidate was REJECTED by the Vision Validator.

Errors:
{errors_text}

Corrections (apply these EXACTLY — use the "parameters" fields if present):
{corrections_text}

INSTRUCTIONS FOR THIS RETRY:
- Correct ONLY the issues listed above.
- Preserve dimensions/orientation that were NOT flagged as errors.
- If a correction says "translate to [x,y,z]", produce a translate op with that exact offset.
- If a correction says "adjust length to N", fix ONLY the length dimension.
- Do NOT randomly regenerate the whole geometry.
- Do NOT repeat the rejected candidate unchanged.
- Do NOT build future steps.
"""
    else:
        feedback_text = ""

    # Inject requirements hint into prompt so LLM also follows structured spec
    if requirements:
        reqs_hint = f"""
STRUCTURED REQUIREMENTS (follow these exactly):
{json.dumps(requirements, indent=2)}

Translate these requirements into the appropriate create_box + translate operations.
Do NOT invent unsupported operations such as create_line, create_edge, create_square.
A "line" = create_box with the long axis matching "direction", thickness for other axes.
"""
    else:
        reqs_hint = ""

    system_prompt = f"""
You are the Builder model in an AI procedural 3D construction system.

Your job is to execute EXACTLY ONE small construction instruction from the Planner.

CRITICAL RULES:
1. Return ONLY valid JSON. No markdown. No explanation.
2. Build ONLY what the Planner instruction specifies.
3. Do NOT recreate objects that already exist.
4. Do NOT build future steps.
5. Use ONLY operations from AVAILABLE OPERATIONS below.
6. NEVER invent operation names.

GEOMETRY MAPPING RULE:
The Planner may say "line", "edge", "side", or "segment".
These are NOT operation names. Translate them:
- A "line" along X (direction=[1,0,0]) = create_box(width=length, height=thickness, depth=thickness) + translate to midpoint
- A "line" along Y (direction=[0,1,0]) = create_box(width=thickness, height=length, depth=thickness) + translate to midpoint
- Never use create_line, create_square, create_rectangle, create_edge.

{feedback_text}
{reqs_hint}
EXISTING SCENE:
{existing_summary}

Total operations already committed: {existing_ops_count}

TARGET OBJECT ID for this step: {target_id}

OUTPUT FORMAT (required exactly):
{{
  "schema_version": "1.0",
  "scene": {{
    "name": "scene",
    "units": "meters"
  }},
  "operations": [
    {{
      "operation": "create_box",
      "parameters": {{
        "id": "{target_id}",
        "width": 1.0,
        "height": 0.05,
        "depth": 0.05
      }}
    }},
    {{
      "operation": "translate",
      "parameters": {{
        "target": "{target_id}",
        "offset": [0.5, 0, 0]
      }}
    }}
  ],
  "constraints": []
}}

PARAMETER RULES:
- "parameters" MUST always be a JSON object (never an array).
- Use parameter names exactly as defined by the operation.
- "schema_version" MUST be "1.0".
- "units" MUST be "meters", "centimeters", or "millimeters".
- "constraints" MUST be an array (can be empty).

AVAILABLE OPERATIONS:
{json.dumps(operations_schema, indent=2)}
"""

    user_content = json.dumps({
        "planner_instruction": step_instruction,
        "current_accepted_state": {
            "objects":          existing_objects,
            "operations_count": existing_ops_count,
        }
    }, indent=2)

    response = ollama.chat(
        model=BUILDER_MODEL,
        format="json",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content}
        ]
    )

    raw_output = response["message"]["content"]
    raw_output = _strip_fences(raw_output)

    try:
        builder_output = json.loads(raw_output)
    except json.JSONDecodeError as e:
        print(f"\n[Builder Error] Failed to parse builder JSON: {e}")
        print(f"[Builder Error] Raw output: {raw_output!r}")
        raise

    # ------------------------------------------------------------------
    # Validate against builder schema
    # ------------------------------------------------------------------
    try:
        validate(instance=builder_output, schema=builder_schema)
    except Exception as schema_err:
        print(f"\n[Builder Error] Builder output failed schema validation: {schema_err}")
        print(f"[Builder Error] Builder output: {json.dumps(builder_output, indent=2)}")
        raise

    # ------------------------------------------------------------------
    # Check for invalid operation names
    # ------------------------------------------------------------------
    bad_ops = [
        op.get("operation")
        for op in builder_output.get("operations", [])
        if op.get("operation") not in ALLOWED_OPERATIONS
    ]
    if bad_ops:
        raise ValueError(
            f"[Builder Error] Builder used disallowed operations: {bad_ops}. "
            f"Allowed: {sorted(ALLOWED_OPERATIONS)}"
        )

    return builder_output


# ------------------------------------------------------------------
# Legacy full-scene builder (kept for backward compatibility)
# ------------------------------------------------------------------

def build_scene(user_prompt: str, scene_plan: dict) -> dict:
    """
    Generate full-scene builder output from a scene plan (legacy).
    """
    response = ollama.chat(
        model=BUILDER_MODEL,
        format=builder_schema,
        messages=[
            {
                "role": "system",
                "content": """
You are the builder stage of an AI procedural 3D system.

Your job is to convert a scene plan into a builder output JSON.

The builder output JSON must conform to the builder schema exactly.
Return ONLY valid JSON. No markdown. No explanation.

Available operations:
- create_box
- create_sphere
- create_cylinder
- create_cone
- create_torus
- translate
- rotate
- scale
- duplicate
- boolean_union
- boolean_difference
- boolean_intersection

"parameters" must always be a JSON object (not an array).
Do not use undefined operations such as create_table, create_chair, etc.
Map conceptual objects to available operations.
"""
            },
            {
                "role": "user",
                "content": json.dumps({
                    "user_request": user_prompt,
                    "scene_plan":   scene_plan,
                }, indent=2)
            }
        ]
    )

    raw_output = response["message"]["content"]

    if raw_output.startswith("```"):
        lines = raw_output.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_output = "\n".join(lines)

    builder_output = json.loads(raw_output)

    try:
        validate(instance=builder_output, schema=builder_schema)
    except Exception as schema_err:
        print(f"\n[Builder Error] Legacy builder output failed schema validation: {schema_err}")
        raise

    return builder_output


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------

if __name__ == "__main__":

    test_instruction = {
        "step_id":    1,
        "instruction": "Create the first line of the square (bottom edge).",
        "target":     "obj_1",
        "requirements": {
            "primitive":  "line",
            "length":     1.0,
            "start":      [0, 0, 0],
            "direction":  [1, 0, 0],
            "thickness":  0.05,
        },
        "is_complete": False,
    }

    accepted_state = {
        "objects":    [],
        "operations": [],
    }

    result = build_next_step(
        step_instruction=test_instruction,
        accepted_state=accepted_state,
    )

    print("\nBuilder Output:")
    print(json.dumps(result, indent=2))