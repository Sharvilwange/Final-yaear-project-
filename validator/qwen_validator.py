"""
Validator module for the AI Procedural 3D system.

Two-level validation:
    Level 1  — Structural (Python/jsonschema):
        validate_builder_output()   schema check on Builder output
        validate_llm_result()       schema check on Validator output (lenient)

    Level 1.5 — Mathematical (Python):
        pre_validate_requirements() — checks candidate ops vs Planner requirements
        (uses geometry.py — same convention as Builder and Renderer)

    Level 2  — Visual (VLM):
        validate_candidate()        — calls qwen2.5vl:3b with rendered image, or
                                      text-only fallback when no image is available.

Vision model: configurable via VISION_MODEL in config.py / env var.
Text fallback: TEXT_VALIDATOR_MODEL in config.py / env var.

SCOPE RULE:
    The VLM validates ONLY the current step.
    A partial scene is EXPECTED and MUST NOT be rejected.
    When the mathematical pre-check passes, the VLM is directed to check
    visual presence ONLY — it must NOT re-measure exact pixel geometry.
"""

import json
import base64
import sys
from pathlib import Path
from jsonschema import validate as jsonschema_validate, ValidationError

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# ------------------------------------------------------------------
# Schema loading
# ------------------------------------------------------------------

VALIDATOR_SCHEMA_PATH = BASE_DIR / "schema" / "validator_schema.json"
with open(VALIDATOR_SCHEMA_PATH, "r", encoding="utf-8") as f:
    validator_schema = json.load(f)

BUILDER_SCHEMA_PATH = BASE_DIR / "schema" / "builder_schema.json"
with open(BUILDER_SCHEMA_PATH, "r", encoding="utf-8") as f:
    builder_schema = json.load(f)

# ------------------------------------------------------------------
# Model configuration — from central config.py
# ------------------------------------------------------------------

from config import VISION_MODEL, TEXT_VALIDATOR_MODEL

# ------------------------------------------------------------------
# Geometry pre-validator
# ------------------------------------------------------------------

from geometry import pre_validate_requirements

import ollama


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


def _load_image_b64(image_path: str) -> str | None:
    """Load image as base64 string for Ollama vision API."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[Validator Warning] Could not load image {image_path}: {e}")
        return None


# ------------------------------------------------------------------
# Structural validation
# ------------------------------------------------------------------

def validate_builder_output(builder_output: dict) -> bool:
    """Validate builder output against builder_schema.json."""
    jsonschema_validate(instance=builder_output, schema=builder_schema)
    return True


def validate_llm_result(validation_result: dict) -> bool:
    """
    Validate LLM validation result against validator_schema.json.

    Lenient mode: if the result contains extra fields not allowed by the schema
    (common with VLMs), strip them and re-validate rather than raising.
    Preserves 'parameters' in corrections since it is now in the schema.
    """
    try:
        jsonschema_validate(instance=validation_result, schema=validator_schema)
        return True
    except ValidationError:
        pass

    # Lenient repair
    clean_result = {
        "valid":       bool(validation_result.get("valid", False)),
        "errors":      [],
        "warnings":    [],
        "corrections": [],
    }

    for err in validation_result.get("errors", []):
        if isinstance(err, dict) and "message" in err:
            clean_result["errors"].append({
                "type":    str(err.get("type", "error")),
                "message": str(err["message"]),
            })

    for warn in validation_result.get("warnings", []):
        if isinstance(warn, dict) and "message" in warn:
            clean_result["warnings"].append({
                "type":    str(warn.get("type", "warning")),
                "message": str(warn["message"]),
            })

    for corr in validation_result.get("corrections", []):
        if isinstance(corr, dict) and "reason" in corr:
            cleaned_corr = {
                "target": str(corr.get("target", "unknown")),
                "action": str(corr.get("action",  "fix")),
                "reason": str(corr["reason"]),
            }
            # Preserve explicit correction parameters — Builder uses these
            if "parameters" in corr and isinstance(corr["parameters"], dict):
                cleaned_corr["parameters"] = corr["parameters"]
            clean_result["corrections"].append(cleaned_corr)

    # Mutate in place so callers see the cleaned version
    validation_result.clear()
    validation_result.update(clean_result)

    jsonschema_validate(instance=validation_result, schema=validator_schema)
    return True


# ------------------------------------------------------------------
# Step-level candidate validator (main function)
# ------------------------------------------------------------------

def validate_candidate(
    user_prompt,
    planner_instruction,
    scene_state,
    builder_output,
    image_path=None,
):
    """
    Validate the current Builder candidate.

    Level 1.5 (Python mathematical pre-check) is always run first.
    Level 2 (VLM visual check) is then called with the pre-check result
    already embedded in the prompt — preventing the VLM from needing to
    measure exact pixel geometry.

    When image_path is None, falls back to TEXT_VALIDATOR_MODEL.
    """

    # ── Level 1.5: Mathematical pre-check ────────────────────────────────────
    requirements   = planner_instruction.get("requirements", {}) or {}
    target_id      = planner_instruction.get("target", "")
    step_id        = planner_instruction.get("step_id", "?")
    instruction    = planner_instruction.get("instruction", "")
    candidate_ops  = builder_output.get("operations", [])

    pre_check = pre_validate_requirements(requirements, candidate_ops, target_id)

    print(f"[VALIDATOR] Mathematical pre-check: {pre_check['passed']} — {pre_check['notes']}")

    # ── Build pre-check section for VLM ─────────────────────────────────────

    if pre_check["passed"] is True:
        exp = pre_check["expected"]
        pre_check_section = f"""
====== MATHEMATICAL PRE-VALIDATION: PASSED ✓ ======
Python has verified that all dimensions and positions in the candidate
match the Planner requirements exactly (within engineering tolerance).

Expected geometry:
{exp.get("description", json.dumps(exp, indent=2))}

CRITICAL INSTRUCTION FOR YOU:
- Do NOT re-evaluate position or length from the image pixels.
- Do NOT reject because of "incorrect position" or "incorrect length"
  if the math has already confirmed they are correct.
- Your ONLY remaining task is to confirm the geometry is VISIBLE
  in the rendered image.
- Accept if the thin elongated box is visible and approximately correct.
- Only reject if the geometry is COMPLETELY ABSENT from the image.
"""
    elif pre_check["passed"] is False:
        exp = pre_check["expected"]
        pre_check_section = f"""
====== MATHEMATICAL PRE-VALIDATION: FAILED ✗ ======
Python has found that the candidate does NOT match requirements.

Issues:
{chr(10).join(f'  - {issue}' for issue in pre_check["issues"])}

Expected geometry:
{exp.get("description", json.dumps(exp, indent=2))}

Reject this candidate and include actionable corrections.
"""
    else:
        pre_check_section = f"""
====== MATHEMATICAL PRE-VALIDATION: N/A ======
No deterministic checker for this primitive type.
Use your visual judgment for both structure and position.
"""

    # ── Accepted objects summary ─────────────────────────────────────────────
    accepted_objects = scene_state.get("objects", [])
    if accepted_objects:
        accepted_summary = "Objects already committed to the accepted scene:\n"
        for obj in accepted_objects:
            accepted_summary += f"  - {obj.get('id')}: {obj.get('type')}\n"
    else:
        accepted_summary = "No objects have been committed yet (this is the first step)."

    # ── VLM prompt ───────────────────────────────────────────────────────────
    prompt = f"""
You are the Vision Validator in an AI procedural 3D construction system.

====== CONSTRUCTION CONTEXT ======
Overall goal: "{user_prompt}"
Current step: Step {step_id} — "{instruction}"
Target object: {target_id}

THIS IS A PARTIAL SCENE.
The complete scene will require multiple steps.
You are validating ONLY the current step (Step {step_id}).

FORBIDDEN REJECTIONS:
- Do NOT reject because the complete goal is not yet achieved.
- Do NOT reject because future geometry is missing.
- Do NOT say "The candidate does not create a {user_prompt}."
- Only reject if THIS STEP'S geometry is incorrect.

====== PLANNER REQUIREMENTS ======
{json.dumps(requirements, indent=2) if requirements else "No structured requirements."}

{pre_check_section}

====== ALREADY ACCEPTED SCENE ======
{accepted_summary}

====== CANDIDATE OPERATIONS (what this step produces) ======
{json.dumps(candidate_ops, indent=2)}

====== IMAGE ======
The attached image (if present) shows the scene after applying the candidate.
Focus only on the NEW geometry introduced by the candidate operations above.
The scene may be empty or contain only previously committed objects before this step.

====== YOUR VALIDATION TASK ======
{
    "Confirm that the expected geometry described above is visually present in the image. "
    "Accept unless the geometry is completely absent. "
    "Do NOT reject for position or length — the Python pre-check already confirmed those."
    if pre_check["passed"] is True else
    "The pre-check found problems. Verify them and provide actionable corrections."
}

====== RESPONSE FORMAT ======
Return ONLY valid JSON. No markdown. No explanation.

If valid:
{{
  "valid": true,
  "errors": [],
  "warnings": [],
  "corrections": []
}}

If invalid, include corrections with explicit parameters where possible:
{{
  "valid": false,
  "errors": [
    {{
      "type": "incorrect_position",
      "message": "The box center is at [0,0,0] but should be at [0.5,0,0]."
    }}
  ],
  "warnings": [],
  "corrections": [
    {{
      "target": "{target_id}",
      "action": "translate",
      "parameters": {{
        "offset": [0.5, 0.0, 0.0]
      }},
      "reason": "Move center of {target_id} to [0.5, 0.0, 0.0]."
    }}
  ]
}}

IMPORTANT for corrections:
- Include a "parameters" object with exact values whenever possible.
- This allows the Builder to directly apply the correction.
- For length: {{"length": 1.0}}
- For position: {{"offset": [x, y, z]}}
- For dimension: {{"width": 1.0, "height": 0.05, "depth": 0.05}}
"""

    # ── Call model ────────────────────────────────────────────────────────────

    if image_path is not None:
        print(f"[VISION VALIDATOR] Model: {VISION_MODEL}")
        print(f"[VISION VALIDATOR] Image: {image_path}")

        response = ollama.chat(
            model=VISION_MODEL,
            format="json",
            messages=[
                {
                    "role":    "user",
                    "content": prompt,
                    "images":  [str(image_path)],
                }
            ]
        )
    else:
        print(f"[VALIDATOR] No image available — text-only fallback model: {TEXT_VALIDATOR_MODEL}")

        response = ollama.chat(
            model=TEXT_VALIDATOR_MODEL,
            format="json",
            messages=[
                {
                    "role":    "system",
                    "content": (
                        "You are a text-only geometry validator. "
                        "Analyse the JSON scene state and builder output carefully. "
                        "Return only valid JSON matching the required schema."
                    ),
                },
                {"role": "user", "content": prompt}
            ]
        )

    raw_response = response["message"]["content"].strip()

    print("\n--- RAW VALIDATOR RESPONSE ---")
    print(raw_response)
    print("--- END RAW VALIDATOR RESPONSE ---")

    raw_response = _strip_fences(raw_response)

    # ── If pre-check passed, override VLM rejection on numerical/scope grounds ─
    # The VLM can still flag geometry that is COMPLETELY ABSENT from the image,
    # but it must NOT override the mathematical result for position/length, and
    # it must NOT reject because the complete goal is not yet achieved (partial
    # scene is expected and must be accepted).
    validation_result = json.loads(raw_response)

    # NOTE: use default False so a missing "valid" key triggers the override check
    if pre_check["passed"] is True and not validation_result.get("valid", False):
        errors = validation_result.get("errors", [])

        # Keywords indicating the VLM is re-evaluating position/dimension —
        # which the Python pre-check has already confirmed as correct.
        numerical_error_keywords = {
            "position", "length", "coordinate", "located", "placed",
            "dimension", "size", "width", "height", "depth", "long",
            "short", "meter", "incorrect length", "incorrect position",
            "center", "offset", "translation", "distance",
        }

        # Keywords indicating the VLM is rejecting because the COMPLETE goal
        # isn't achieved yet — this is a forbidden scope rejection for a
        # partial/incremental build.
        scope_rejection_keywords = {
            "square", "complete", "incomplete", "missing side", "missing edge",
            "not a square", "only", "partial", "does not form", "not yet",
            "future step", "remaining", "not complete", "not finished",
        }

        def _is_overridable(err: dict) -> bool:
            combined = (err.get("message", "") + " " + err.get("type", "")).lower()
            return (
                any(kw in combined for kw in numerical_error_keywords)
                or any(kw in combined for kw in scope_rejection_keywords)
            )

        all_overridable = errors and all(_is_overridable(e) for e in errors)

        if all_overridable:
            print(
                "[VALIDATOR Override] Pre-check PASSED but VLM rejected on "
                "numerical or scope grounds. Overriding to VALID — "
                "the Python math is authoritative for geometry; "
                "partial scenes must be accepted."
            )
            validation_result = {
                "valid":       True,
                "errors":      [],
                "warnings": [
                    {
                        "type":    "pre_check_override",
                        "message": (
                            "VLM rejected on numerical or scope grounds but Python "
                            "pre-check confirmed geometry is correct. "
                            "Accepting candidate."
                        ),
                    }
                ],
                "corrections": [],
            }

    # Lenient schema validation — strips extra VLM fields without crashing
    validate_llm_result(validation_result)

    return validation_result


# ------------------------------------------------------------------
# Legacy full-scene validator (used by original __main__ flow)
# ------------------------------------------------------------------

def run_llm_validator(user_prompt: str, scene_plan: dict, builder_output: dict) -> dict:
    """
    Full-scene LLM validator (legacy).
    Checks whether the entire builder_output satisfies the scene_plan.
    """
    response = ollama.chat(
        model=TEXT_VALIDATOR_MODEL,
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

Return ONLY valid JSON:

{
  "valid": true,
  "errors": [],
  "warnings": [],
  "corrections": []
}

Every error or warning MUST contain "type" and "message".
Every correction MUST contain "target", "action", and "reason".
"""
            },
            {
                "role": "user",
                "content": json.dumps({
                    "user_request":  user_prompt,
                    "scene_plan":    scene_plan,
                    "builder_output": builder_output,
                }, indent=2)
            }
        ]
    )

    raw_response = response["message"]["content"].strip()
    raw_response = _strip_fences(raw_response)
    return json.loads(raw_response)


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------

if __name__ == "__main__":

    result = validate_candidate(
        user_prompt="Create a square",

        planner_instruction={
            "step_id":     1,
            "instruction": "Create the first line of the square (bottom edge).",
            "target":      "obj_1",
            "requirements": {
                "primitive":  "line",
                "length":     1.0,
                "start":      [0, 0, 0],
                "direction":  [1, 0, 0],
                "thickness":  0.05,
            },
        },

        scene_state={
            "objects":    [],
            "operations": [],
        },

        builder_output={
            "schema_version": "1.0",
            "scene":          {"name": "scene_001", "units": "meters"},
            "operations": [
                {
                    "operation":  "create_box",
                    "parameters": {"id": "obj_1", "width": 1.0, "height": 0.05, "depth": 0.05},
                },
                {
                    "operation":  "translate",
                    "parameters": {"target": "obj_1", "offset": [0.5, 0.0, 0.0]},
                }
            ],
            "constraints": [],
        },

        image_path=None  # text-only fallback
    )

    print("\nValidator Result:")
    print(json.dumps(result, indent=2))