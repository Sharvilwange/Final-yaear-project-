"""
Scene Registry — Single source of truth for the accepted scene state.

Candidate lifecycle:
    set_candidate()  → stores candidate (does NOT modify accepted state)
    commit_candidate() → merges candidate into accepted state
    reject_candidate() → discards candidate, accepted state unchanged
"""


class SceneRegistry:

    def __init__(self, scene_id, goal):
        self.state = {
            "scene_id": scene_id,
            "goal": goal,
            "stage": "planning",
            "status": "in_progress",

            # Accepted geometry (only committed candidates appear here)
            "objects": [],
            "operations": [],

            # Temporary candidate — NOT part of accepted state
            "candidate": None,

            # Current Planner instruction
            "current_step": None,

            # Ordered list of completed step summaries (for Planner progress tracking)
            "completed_steps": [],

            "validation": {
                "status": "not_checked",
                "errors": [],
                "warnings": [],
                "corrections": []
            }
        }

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_state(self):
        """Return the full internal state (for debugging/logging only)."""
        return self.state

    def get_accepted_state(self):
        """
        Return a clean view of the ACCEPTED scene state.
        This is what Planner, Builder, and Validator should see.
        Excludes the candidate and internal validation state.
        """
        return {
            "scene_id": self.state["scene_id"],
            "goal": self.state["goal"],
            "stage": self.state["stage"],
            "objects": list(self.state["objects"]),
            "operations": list(self.state["operations"]),
            "completed_steps": list(self.state["completed_steps"]),
        }

    def get_candidate(self):
        return self.state["candidate"]

    def get_next_step_id(self):
        """Derive the authoritative next step ID from the number of completed steps."""
        return len(self.state["completed_steps"]) + 1

    # ------------------------------------------------------------------
    # Write — Planner
    # ------------------------------------------------------------------

    def set_step(self, step):
        self.state["current_step"] = step

    # ------------------------------------------------------------------
    # Write — Candidate lifecycle
    # ------------------------------------------------------------------

    def set_candidate(self, candidate):
        """Store candidate without touching accepted state."""
        self.state["candidate"] = candidate

    def clear_candidate(self):
        self.state["candidate"] = None

    def update_validation(self, result):
        self.state["validation"] = result

    def commit_candidate(self):
        """
        Commit the current candidate to accepted state.
        Returns True on success, False if no candidate or no operations.
        """
        if self.state["candidate"] is None:
            return False

        candidate_ops = self.state["candidate"].get("operations", [])

        # Guard: do NOT record a completed step for an empty candidate.
        # An empty ops list means the Builder produced nothing useful.
        if not candidate_ops:
            print("[Registry Warning] commit_candidate() called with 0 operations — skipping.")
            self.clear_candidate()
            return False

        self.state["operations"].extend(candidate_ops)

        # Extract objects from create_* operations
        for op in candidate_ops:
            op_name = op.get("operation", "")
            params = op.get("parameters", {})
            if op_name.startswith("create_") and "id" in params:
                obj_id = params["id"]
                obj_type = op_name.replace("create_", "")
                if not any(o.get("id") == obj_id for o in self.state["objects"]):
                    self.state["objects"].append({
                        "id": obj_id,
                        "type": obj_type
                    })

        # Record the completed step
        step = self.state.get("current_step")
        if step:
            self.state["completed_steps"].append({
                "step_id": step.get("step_id"),
                "instruction": step.get("instruction", ""),
                "target": step.get("target", ""),
                "ops_committed": len(candidate_ops)
            })

        self.clear_candidate()
        self.state["validation"] = {
            "status": "validated",
            "errors": [],
            "warnings": [],
            "corrections": []
        }
        return True

    def reject_candidate(self, validation_result=None):
        """
        Reject the current candidate. Accepted state is UNCHANGED.
        Returns False.
        """
        self.clear_candidate()

        if validation_result is not None:
            # Normalize: ensure "valid" key exists (schema requirement)
            if "valid" not in validation_result:
                validation_result = dict(validation_result)
                validation_result["valid"] = False
            self.state["validation"] = validation_result
        else:
            self.state["validation"] = {
                "valid": False,
                "status": "rejected",
                "errors": [{"type": "rejection", "message": "Candidate rejected"}],
                "warnings": [],
                "corrections": []
            }
        return False

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def commit(self, operations):
        """Direct operation commit (legacy/test helper)."""
        self.state["operations"].extend(operations)

    def set_stage(self, stage):
        self.state["stage"] = stage

    def set_status(self, status):
        self.state["status"] = status