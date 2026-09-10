"""
Construction Loop — Core orchestration for the AI Procedural 3D system.

Architecture:
    User Prompt
      -> SceneRegistry
      -> Planner (DeepSeek R1 7B) generates NEXT STEP instruction
      -> Builder (Qwen 2.5) generates candidate operations
      -> Structural validation (builder_schema.json)
      -> Registry.set_candidate()
      -> Renderer produces image
      -> Validator (DeepSeek R1 7B) validates candidate
      -> VALID  -> Registry.commit_candidate() -> next step
      -> INVALID -> Registry.reject_candidate() -> retry (up to MAX_RETRIES)
      -> Completion detection via Planner.is_complete or max_steps
"""

import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from state.scene_registry import SceneRegistry
from planner.deepseek_thinker import generate_next_instruction
from builder.qwen_builder import build_next_step
from validator.qwen_validator import validate_builder_output, validate_candidate

MAX_RETRIES = 3

# Try to import renderer (optional — if matplotlib not available, skip rendering)
try:
    from renderer.scene_renderer import render_candidate
    RENDERER_AVAILABLE = True
except ImportError:
    RENDERER_AVAILABLE = False
    print("[Loop Warning] Renderer not available. Running without image rendering.")


def run_construction_loop(
    user_prompt: str,
    max_steps: int = 10,
    scene_id: str = "scene_001"
) -> dict:
    """
    Run the full iterative procedural 3D construction loop.

    Parameters:
        user_prompt: Natural language description of the desired 3D scene.
        max_steps:   Maximum number of construction steps before stopping.
        scene_id:    Unique identifier for the scene.

    Returns:
        Final scene registry state dict.
    """

    registry = SceneRegistry(scene_id, user_prompt)
    registry.set_stage("construction")

    print(f"\n{'='*60}")
    print(f"Starting construction: {user_prompt!r}")
    print(f"Max steps: {max_steps}, Max retries per step: {MAX_RETRIES}")
    print(f"{'='*60}")

    for step_count in range(1, max_steps + 1):
        print(f"\n{'='*60}")
        print(f"STEP {step_count} / {max_steps}")
        print(f"{'='*60}")

        # ----------------------------------------------------------
        # 1. Get current ACCEPTED state (clean view for LLMs)
        # ----------------------------------------------------------
        accepted_state = registry.get_accepted_state()
        completed = accepted_state.get("completed_steps", [])

        print(f"[STATE] Accepted objects: {len(accepted_state.get('objects', []))}")
        print(f"[STATE] Completed steps so far: {len(completed)}")

        # ----------------------------------------------------------
        # 2. Planner generates NEXT instruction
        # ----------------------------------------------------------
        print(f"\n[PLANNER] Generating next instruction for goal: {user_prompt!r}")
        try:
            step_instruction = generate_next_instruction(user_prompt, accepted_state)
        except Exception as e:
            print(f"[PLANNER ERROR] Failed to generate instruction: {e}")
            registry.set_status("failed")
            break

        # Override step_id to be authoritative (based on registry)
        step_instruction["step_id"] = registry.get_next_step_id()

        print(f"[PLANNER] Step {step_instruction['step_id']}: {step_instruction.get('instruction')}")
        print(f"[PLANNER] Target: {step_instruction.get('target')}")
        reqs = step_instruction.get('requirements', {})
        if reqs:
            print(f"[PLANNER] Requirements: primitive={reqs.get('primitive','?')} "
                  f"start={reqs.get('start','?')} direction={reqs.get('direction','?')} "
                  f"length={reqs.get('length','?')} thickness={reqs.get('thickness','?')}")
        print(f"[PLANNER] Is complete signal: {step_instruction.get('is_complete', False)}")

        # ----------------------------------------------------------
        # 3. Completion detection — Planner signals done
        # ----------------------------------------------------------
        if step_instruction.get("is_complete", False):
            print(f"\n[LOOP] Planner signaled GOAL COMPLETE after {len(completed)} committed steps.")
            registry.set_stage("complete")
            registry.set_status("completed")
            break

        # Store current instruction in registry
        registry.set_step(step_instruction)

        # ----------------------------------------------------------
        # 4. Builder retry loop
        # ----------------------------------------------------------
        retry_count = 0
        step_committed = False
        validation_feedback = None   # latest Validator result; passed to next retry
        prev_candidate_ops = None    # track previous ops to detect unchanged retries
        while retry_count < MAX_RETRIES:
            attempt = retry_count + 1
            print(f"\n[BUILDER] Generating candidate (Attempt {attempt}/{MAX_RETRIES})...")

            # Always use accepted_state (not full registry state)
            current_accepted = registry.get_accepted_state()

            # 4a. Build candidate
            try:
                candidate_output = build_next_step(
                    step_instruction,
                    current_accepted,
                    registry, # We set candidate manually below
                    validation_feedback
                )
            except Exception as e:
                print(f"[BUILDER ERROR] Build failed: {e}")
                retry_count += 1
                continue

            # 4b. Structural schema validation
            try:
                validate_builder_output(candidate_output)
                print(f"[BUILDER] Schema validation: PASSED")
                print(f"[BUILDER] Operations: {len(candidate_output.get('operations', []))}")
            except Exception as e:
                print(f"[BUILDER ERROR] Schema validation failed: {e}")
                retry_count += 1
                continue

            # 4b-ii. Detect unchanged retry candidate (oscillation guard)
            new_ops = candidate_output.get("operations", [])
            new_ops_key = json.dumps(new_ops, sort_keys=True)
            if prev_candidate_ops is not None and new_ops_key == prev_candidate_ops:
                print("[BUILDER WARNING] Retry candidate UNCHANGED after validator feedback. "
                      "Builder did not apply the correction.")
            prev_candidate_ops = new_ops_key

            # 4c. Store as candidate (does NOT touch accepted state)
            registry.set_candidate(candidate_output)
            print(f"[REGISTRY] Candidate set ({len(candidate_output.get('operations', []))} operations)")

            # 4d. Render candidate
            image_path = None
            if RENDERER_AVAILABLE:
                try:
                    image_path = render_candidate(
                        current_accepted,
                        candidate_output,
                        output_filename=f"step_{step_instruction['step_id']}_attempt_{attempt}.png"
                    )
                except Exception as e:
                    print(f"[RENDERER Warning] Render failed: {e}")
                    image_path = None

            # 4e. Validate candidate
            print(f"[VALIDATOR] Validating candidate...")
            try:
                validation_result = validate_candidate(
                    user_prompt=user_prompt,
                    planner_instruction=step_instruction,
                    scene_state=current_accepted,
                    builder_output=candidate_output,
                    image_path=image_path
                )
            except Exception as e:
                print(f"[VALIDATOR ERROR] Validation failed with exception: {e}")
                validation_result = {
                    "valid": False,
                    "errors": [{"type": "exception", "message": str(e)}],
                    "warnings": [],
                    "corrections": []
                }

            is_valid = validation_result.get("valid", False)
            print(f"[VALIDATOR] Result: {'VALID' if is_valid else 'INVALID'}")

            if not is_valid:
                # Always use the LATEST feedback for the next retry
                validation_feedback = validation_result
                errors = validation_result.get("errors", [])
                for err in errors:
                    print(f"  ERROR [{err.get('type')}]: {err.get('message')}")
                corrections = validation_result.get("corrections", [])
                for corr in corrections:
                    params_str = f" params={corr.get('parameters')}" if corr.get('parameters') else ""
                    print(f"  CORRECTION [{corr.get('target')}]: {corr.get('action')}{params_str} — {corr.get('reason')}")

            # 4f. Commit or reject
            if is_valid:
                registry.update_validation(validation_result)
                registry.commit_candidate()
                print(f"\n[REGISTRY] Candidate COMMITTED to accepted state.")
                print(f"[REGISTRY] Accepted objects now: {len(registry.get_accepted_state().get('objects', []))}")
                print(f"[REGISTRY] Completed steps now: {len(registry.get_accepted_state().get('completed_steps', []))}")
                step_committed = True
                break

            else:
                registry.reject_candidate(validation_result)
                print(f"[REGISTRY] Candidate REJECTED. Accepted state UNCHANGED.")
                retry_count += 1

        # ----------------------------------------------------------
        # 5. Handle max retries exceeded
        # ----------------------------------------------------------
        if not step_committed:
            print(f"\n[LOOP WARNING] Step {step_count} FAILED after {MAX_RETRIES} attempts.")
            print(f"[LOOP WARNING] Halting construction loop.")
            registry.set_status("failed")
            break

    # ----------------------------------------------------------
    # 6. Finalization
    # ----------------------------------------------------------
    final_state = registry.get_state()
    if final_state.get("status") not in ("completed", "failed"):
        registry.set_stage("complete")
        registry.set_status("partial")

    print(f"\n{'='*60}")
    print("CONSTRUCTION LOOP FINISHED")
    print(f"Status: {registry.get_state().get('status')}")
    print(f"Committed steps: {len(registry.get_accepted_state().get('completed_steps', []))}")
    print(f"Accepted objects: {len(registry.get_accepted_state().get('objects', []))}")
    print(f"Total accepted operations: {len(registry.get_accepted_state().get('operations', []))}")
    print(f"{'='*60}")

    return registry.get_state()


# ------------------------------------------------------------------
# Standalone runner
# ------------------------------------------------------------------

if __name__ == "__main__":
    prompt = input("Enter 3D scene prompt (default: 'Create a square'): ").strip()
    if not prompt:
        prompt = "Create a square"

    final_state = run_construction_loop(prompt, max_steps=6)

    print("\n==========================================")
    print("FINAL SCENE REGISTRY STATE:")
    print("==========================================")

    # Print clean version (exclude huge ops lists for readability)
    summary = {
        "scene_id": final_state.get("scene_id"),
        "goal": final_state.get("goal"),
        "stage": final_state.get("stage"),
        "status": final_state.get("status"),
        "objects": final_state.get("objects"),
        "completed_steps": final_state.get("completed_steps"),
        "total_operations": len(final_state.get("operations", []))
    }
    print(json.dumps(summary, indent=2))
