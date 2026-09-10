"""
Python renderer for the AI Procedural 3D system.

render_candidate(accepted_state, candidate_output) → image_path

Uses matplotlib to render a 3D wireframe view of the scene.
The candidate is merged with the accepted state in a TEMPORARY view
so the accepted state is NEVER modified.

This renderer produces images suitable for passing to a vision model.
"""

import json
import os
import tempfile
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("[Renderer Warning] matplotlib not available. Rendering disabled.")

# Output directory for rendered images
RENDER_DIR = Path(__file__).resolve().parent.parent / "renders"
RENDER_DIR.mkdir(exist_ok=True)


def _box_faces(cx, cy, cz, w, h, d):
    """
    Return the 6 faces of a box as a list of polygons.
    Each polygon is a list of 4 vertices (x, y, z).
    cx, cy, cz = center; w, h, d = width, height, depth
    """
    hw, hh, hd = w / 2, h / 2, d / 2
    # Vertices
    v = [
        (cx - hw, cy - hh, cz - hd),  # 0 front-bottom-left
        (cx + hw, cy - hh, cz - hd),  # 1 front-bottom-right
        (cx + hw, cy + hh, cz - hd),  # 2 front-top-right
        (cx - hw, cy + hh, cz - hd),  # 3 front-top-left
        (cx - hw, cy - hh, cz + hd),  # 4 back-bottom-left
        (cx + hw, cy - hh, cz + hd),  # 5 back-bottom-right
        (cx + hw, cy + hh, cz + hd),  # 6 back-top-right
        (cx - hw, cy + hh, cz + hd),  # 7 back-top-left
    ]
    faces = [
        [v[0], v[1], v[2], v[3]],  # front
        [v[4], v[5], v[6], v[7]],  # back
        [v[0], v[4], v[7], v[3]],  # left
        [v[1], v[5], v[6], v[2]],  # right
        [v[0], v[1], v[5], v[4]],  # bottom
        [v[3], v[2], v[6], v[7]],  # top
    ]
    return faces


def _apply_operations(operations: list) -> list:
    """
    Interpret a list of operations and return a list of drawable objects.
    Each drawable: {"type": "box", "cx": x, "cy": y, "cz": z, "w": w, "h": h, "d": d, "label": id, "color": ...}
    """
    object_registry = {}  # id -> position/params
    drawables = []

    for op in operations:
        op_name = op.get("operation", "")
        params = op.get("parameters", {})

        if op_name == "create_box":
            obj_id = params.get("id", "obj")
            w = float(params.get("width", 1.0))
            h = float(params.get("height", 1.0))
            d = float(params.get("depth", 1.0))
            object_registry[obj_id] = {
                "cx": 0.0, "cy": 0.0, "cz": 0.0,
                "w": w, "h": h, "d": d,
                "label": obj_id
            }

        elif op_name == "create_sphere":
            obj_id = params.get("id", "obj")
            r = float(params.get("radius", 0.5))
            object_registry[obj_id] = {
                "cx": 0.0, "cy": 0.0, "cz": 0.0,
                "w": r * 2, "h": r * 2, "d": r * 2,
                "label": obj_id
            }

        elif op_name == "create_cylinder":
            obj_id = params.get("id", "obj")
            r = float(params.get("radius", 0.5))
            h = float(params.get("height", 1.0))
            object_registry[obj_id] = {
                "cx": 0.0, "cy": 0.0, "cz": 0.0,
                "w": r * 2, "h": h, "d": r * 2,
                "label": obj_id
            }

        elif op_name == "create_cone":
            obj_id = params.get("id", "obj")
            r = float(params.get("radius", 0.5))
            h = float(params.get("height", 1.0))
            object_registry[obj_id] = {
                "cx": 0.0, "cy": 0.0, "cz": 0.0,
                "w": r * 2, "h": h, "d": r * 2,
                "label": obj_id
            }

        elif op_name == "create_plane":
            obj_id = params.get("id", "obj")
            w = float(params.get("width", 1.0))
            h_p = float(params.get("height", 1.0))
            object_registry[obj_id] = {
                "cx": 0.0, "cy": 0.0, "cz": 0.0,
                "w": w, "h": 0.02, "d": h_p,
                "label": obj_id
            }

        elif op_name == "create_torus":
            obj_id = params.get("id", "obj")
            r = float(params.get("radius", 1.0))
            object_registry[obj_id] = {
                "cx": 0.0, "cy": 0.0, "cz": 0.0,
                "w": r * 2, "h": 0.3, "d": r * 2,
                "label": obj_id
            }

        elif op_name == "translate":
            target_id = params.get("target", "")
            offset = params.get("offset", [0, 0, 0])
            if target_id in object_registry:
                object_registry[target_id]["cx"] += float(offset[0] if len(offset) > 0 else 0)
                object_registry[target_id]["cy"] += float(offset[1] if len(offset) > 1 else 0)
                object_registry[target_id]["cz"] += float(offset[2] if len(offset) > 2 else 0)

        elif op_name == "rotate":
            pass  # Visual rotation not critical for step validation

        elif op_name == "scale":
            target_id = params.get("target", "")
            factor = params.get("factor", 1.0)
            if target_id in object_registry:
                obj = object_registry[target_id]
                if isinstance(factor, (int, float)):
                    obj["w"] *= factor
                    obj["h"] *= factor
                    obj["d"] *= factor
                elif isinstance(factor, list) and len(factor) == 3:
                    obj["w"] *= factor[0]
                    obj["h"] *= factor[1]
                    obj["d"] *= factor[2]

        elif op_name == "duplicate":
            target_id = params.get("target", "")
            new_id = params.get("new_id", "")
            if target_id in object_registry and new_id:
                import copy
                clone = copy.deepcopy(object_registry[target_id])
                clone["label"] = new_id
                object_registry[new_id] = clone

        elif op_name == "repeat":
            target_id = params.get("target", "")
            count = int(params.get("count", 1))
            offset = params.get("offset", [0, 0, 0])
            if target_id in object_registry:
                import copy
                for i in range(1, count):
                    clone = copy.deepcopy(object_registry[target_id])
                    clone["cx"] += float(offset[0]) * i
                    clone["cy"] += float(offset[1]) * i
                    clone["cz"] += float(offset[2]) * i
                    clone_id = f"{target_id}_repeat_{i}"
                    clone["label"] = clone_id
                    object_registry[clone_id] = clone

        # group/combine/extrude/mirror: add objects but skip visual complexity

    # Convert registry to drawables
    for obj_id, obj in object_registry.items():
        drawables.append(obj)

    return drawables


def render_candidate(
    accepted_state: dict,
    candidate_output: dict,
    output_filename: str = None
) -> str:
    """
    Render the accepted state + candidate operations to a PNG image.

    The accepted state is NOT modified. The render is performed on a
    temporary merged view.

    Parameters:
        accepted_state:    Clean accepted state from registry.get_accepted_state().
        candidate_output:  Builder candidate (not yet committed).
        output_filename:   Optional filename for the output PNG.

    Returns:
        Absolute path to the rendered PNG file, or None if rendering failed.
    """

    if not MATPLOTLIB_AVAILABLE:
        print("[Renderer] matplotlib not available, skipping render.")
        return None

    try:
        # Merge accepted operations + candidate operations (temporary, read-only)
        accepted_ops = accepted_state.get("operations", [])
        candidate_ops = candidate_output.get("operations", [])

        all_ops = list(accepted_ops) + list(candidate_ops)

        # Apply operations to get drawables
        drawables = _apply_operations(all_ops)
        candidate_drawables = _apply_operations(candidate_ops)
        candidate_ids = {d["label"] for d in candidate_drawables}

        # Setup figure
        fig = plt.figure(figsize=(8, 7), dpi=100)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_title("Scene Preview — Candidate + Accepted State", fontsize=10, pad=10)

        for obj in drawables:
            cx = obj.get("cx", 0.0)
            cy = obj.get("cy", 0.0)
            cz = obj.get("cz", 0.0)
            w = max(obj.get("w", 1.0), 0.01)
            h = max(obj.get("h", 1.0), 0.01)
            d = max(obj.get("d", 1.0), 0.01)
            label = obj.get("label", "")

            is_candidate = label in candidate_ids
            facecolor = "lightcoral" if is_candidate else "lightsteelblue"
            alpha = 0.7 if is_candidate else 0.4
            edgecolor = "red" if is_candidate else "steelblue"

            faces = _box_faces(cx, cy, cz, w, h, d)
            poly = Poly3DCollection(
                faces,
                facecolor=facecolor,
                edgecolor=edgecolor,
                alpha=alpha,
                linewidth=0.8
            )
            ax.add_collection3d(poly)

            # Label
            ax.text(
                cx, cy, cz + h / 2 + 0.05,
                label,
                fontsize=7,
                ha="center",
                color="darkred" if is_candidate else "darkblue"
            )

        # Auto-scale axes
        if drawables:
            all_cx = [d["cx"] for d in drawables]
            all_cy = [d["cy"] for d in drawables]
            all_cz = [d["cz"] for d in drawables]
            margin = 0.5
            ax.set_xlim(min(all_cx) - margin, max(all_cx) + margin)
            ax.set_ylim(min(all_cy) - margin, max(all_cy) + margin)
            ax.set_zlim(min(all_cz) - margin, max(all_cz) + 1.0)
        else:
            ax.set_xlim(-1, 2)
            ax.set_ylim(-1, 2)
            ax.set_zlim(-1, 2)

        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")

        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="lightsteelblue", edgecolor="steelblue", label="Accepted (committed)"),
            Patch(facecolor="lightcoral", edgecolor="red", label="Candidate (pending validation)")
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=8)

        ax.view_init(elev=25, azim=-60)

        # Save
        if output_filename is None:
            output_filename = f"candidate_render.png"

        output_path = RENDER_DIR / output_filename
        plt.tight_layout()
        plt.savefig(str(output_path), dpi=100, bbox_inches="tight")
        plt.close(fig)

        print(f"[Renderer] Scene rendered to: {output_path}")
        return str(output_path)

    except Exception as e:
        print(f"[Renderer Error] Failed to render scene: {e}")
        import traceback
        traceback.print_exc()
        return None


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------

if __name__ == "__main__":
    accepted_state = {
        "objects": [{"id": "obj_1", "type": "box"}],
        "operations": [
            {
                "operation": "create_box",
                "parameters": {"id": "obj_1", "width": 1.0, "height": 0.05, "depth": 0.05}
            }
        ],
        "completed_steps": [
            {"step_id": 1, "instruction": "Create the first line of the square."}
        ]
    }

    candidate_output = {
        "schema_version": "1.0",
        "scene": {"name": "scene_001", "units": "meters"},
        "operations": [
            {
                "operation": "create_box",
                "parameters": {"id": "obj_2", "width": 0.05, "height": 1.0, "depth": 0.05}
            },
            {
                "operation": "translate",
                "parameters": {"target": "obj_2", "offset": [0.975, 0.0, 0.0]}
            }
        ],
        "constraints": []
    }

    image_path = render_candidate(accepted_state, candidate_output, "test_render.png")
    if image_path:
        print(f"Render saved to: {image_path}")
    else:
        print("Render failed.")
