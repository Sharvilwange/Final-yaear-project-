"""
Semantic validation layer for AI Procedural 3D scenes.
Validates object lifecycle, target references, uniqueness, parameter domains, and constraint integrity.
"""


def semantic_validate(scene):
    """
    Performs semantic validation on a procedural 3D scene dictionary.

    Returns:
        list[str]: A list of human-readable error messages. Empty if valid.
    """
    errors = []

    if not isinstance(scene, dict):
        return ["Scene root must be a JSON object"]

    operations = scene.get("operations", [])
    if not isinstance(operations, list):
        return ["'operations' must be an array"]

    operation_ids = set()
    created_objects = set()

    for idx, operation in enumerate(operations):
        if not isinstance(operation, dict):
            errors.append(f"Operation at index {idx} is not an object")
            continue

        operation_id = operation.get("id", f"op_index_{idx}")
        operation_type = operation.get("type")

        # ----------------------------------------------------
        # 1. Operation ID uniqueness
        # ----------------------------------------------------
        if operation_id in operation_ids:
            errors.append(f"Duplicate operation ID: '{operation_id}'")
        operation_ids.add(operation_id)

        parameters = operation.get("parameters", {})
        if not isinstance(parameters, dict):
            errors.append(f"{operation_id}: 'parameters' must be an object")
            parameters = {}

        # ----------------------------------------------------
        # 2. Object Creation & ID uniqueness
        # ----------------------------------------------------
        if isinstance(operation_type, str) and operation_type.startswith("create_"):
            object_id = parameters.get("id")

            if not object_id or not isinstance(object_id, str):
                errors.append(f"{operation_id}: Creation operation '{operation_type}' missing valid 'id' parameter")
            elif object_id in created_objects:
                errors.append(f"{operation_id}: Duplicate object ID '{object_id}' already exists")
            else:
                created_objects.add(object_id)

            # Geometry parameter sanity checks
            if operation_type == "create_box":
                for dim in ["width", "height", "depth"]:
                    val = parameters.get(dim)
                    if val is not None and (not isinstance(val, (int, float)) or val <= 0):
                        errors.append(f"{operation_id}: '{dim}' must be a positive number (got {val})")

            elif operation_type in ["create_sphere", "create_cylinder", "create_cone"]:
                radius = parameters.get("radius")
                if radius is not None and (not isinstance(radius, (int, float)) or radius <= 0):
                    errors.append(f"{operation_id}: 'radius' must be a positive number (got {radius})")

                if operation_type in ["create_cylinder", "create_cone"]:
                    height = parameters.get("height")
                    if height is not None and (not isinstance(height, (int, float)) or height <= 0):
                        errors.append(f"{operation_id}: 'height' must be a positive number (got {height})")

            elif operation_type == "create_plane":
                for dim in ["width", "height"]:
                    val = parameters.get(dim)
                    if val is not None and (not isinstance(val, (int, float)) or val <= 0):
                        errors.append(f"{operation_id}: '{dim}' must be a positive number (got {val})")

            elif operation_type == "create_torus":
                for dim in ["radius", "tube"]:
                    val = parameters.get(dim)
                    if val is not None and (not isinstance(val, (int, float)) or val <= 0):
                        errors.append(f"{operation_id}: '{dim}' must be a positive number (got {val})")

        # ----------------------------------------------------
        # 3. Duplicate Operation
        # ----------------------------------------------------
        elif operation_type == "duplicate":
            target = operation.get("target") or parameters.get("target")
            new_id = parameters.get("new_id")

            if not target:
                errors.append(f"{operation_id}: 'duplicate' missing 'target'")
            elif target not in created_objects:
                errors.append(f"{operation_id}: Target object '{target}' does not exist")

            if not new_id or not isinstance(new_id, str):
                errors.append(f"{operation_id}: 'duplicate' missing valid 'new_id' parameter")
            elif new_id in created_objects:
                errors.append(f"{operation_id}: Duplicate object ID '{new_id}' already exists")
            else:
                created_objects.add(new_id)

        # ----------------------------------------------------
        # 4. Group Operation
        # ----------------------------------------------------
        elif operation_type == "group":
            group_id = parameters.get("id")
            objects = parameters.get("objects", [])

            if not group_id or not isinstance(group_id, str):
                errors.append(f"{operation_id}: 'group' missing valid 'id' parameter")
            elif group_id in created_objects:
                errors.append(f"{operation_id}: Duplicate object ID '{group_id}' already exists")
            else:
                created_objects.add(group_id)

            if not isinstance(objects, list) or len(objects) == 0:
                errors.append(f"{operation_id}: 'group' objects list must be a non-empty array")
            else:
                for obj in objects:
                    if obj not in created_objects:
                        errors.append(f"{operation_id}: Group member '{obj}' does not exist")

        # ----------------------------------------------------
        # 5. Combine Operation
        # ----------------------------------------------------
        elif operation_type == "combine":
            objects = parameters.get("objects", [])
            if not isinstance(objects, list) or len(objects) == 0:
                errors.append(f"{operation_id}: 'combine' objects list must be a non-empty array")
            else:
                for obj in objects:
                    if obj not in created_objects:
                        errors.append(f"{operation_id}: Combine member '{obj}' does not exist")

        # ----------------------------------------------------
        # 6. Target Transformations & Manipulations
        # ----------------------------------------------------
        elif operation_type in ["translate", "rotate", "scale", "repeat", "mirror", "extrude"]:
            target = operation.get("target") or parameters.get("target")

            if not target:
                errors.append(f"{operation_id}: Operation '{operation_type}' missing 'target'")
            elif target not in created_objects:
                errors.append(f"{operation_id}: Target object '{target}' does not exist")

            # Specific modifier validation
            if operation_type == "scale":
                factor = parameters.get("factor")
                if factor is None:
                    errors.append(f"{operation_id}: 'scale' missing 'factor' parameter")
                elif isinstance(factor, (int, float)):
                    if factor <= 0:
                        errors.append(f"{operation_id}: Scale factor must be positive (got {factor})")
                elif isinstance(factor, list):
                    if len(factor) != 3 or not all(isinstance(v, (int, float)) and v > 0 for v in factor):
                        errors.append(f"{operation_id}: Scale factor vector must have 3 positive numbers (got {factor})")
                else:
                    errors.append(f"{operation_id}: Scale factor must be a positive number or 3D vector")

            elif operation_type == "repeat":
                count = parameters.get("count")
                if count is None:
                    errors.append(f"{operation_id}: 'repeat' missing 'count' parameter")
                elif not isinstance(count, int) or count < 1:
                    errors.append(f"{operation_id}: Repeat count must be a positive integer >= 1 (got {count})")

                offset = parameters.get("offset")
                if offset is not None:
                    if not isinstance(offset, list) or len(offset) != 3 or not all(isinstance(v, (int, float)) for v in offset):
                        errors.append(f"{operation_id}: Repeat offset must be a 3D vector [x, y, z]")

            elif operation_type == "mirror":
                axis = parameters.get("axis")
                valid_axes_strings = ["x", "y", "z", "X", "Y", "Z", "+x", "-x", "+y", "-y", "+z", "-z"]
                if axis is None:
                    errors.append(f"{operation_id}: 'mirror' missing 'axis' parameter")
                elif isinstance(axis, str):
                    if axis not in valid_axes_strings:
                        errors.append(f"{operation_id}: Invalid mirror axis '{axis}' (allowed: {valid_axes_strings})")
                elif isinstance(axis, list):
                    if len(axis) != 3 or not all(isinstance(v, (int, float)) for v in axis) or all(v == 0 for v in axis):
                        errors.append(f"{operation_id}: Mirror axis vector must be a non-zero 3D vector [x, y, z]")
                else:
                    errors.append(f"{operation_id}: Mirror axis must be a string (e.g. 'x', 'y', 'z') or 3D vector")

            elif operation_type == "extrude":
                distance = parameters.get("distance")
                if distance is None:
                    errors.append(f"{operation_id}: 'extrude' missing 'distance' parameter")
                elif not isinstance(distance, (int, float)) or distance == 0:
                    errors.append(f"{operation_id}: Extrude distance must be a non-zero number (got {distance})")

    # ----------------------------------------------------
    # 7. Constraints Validation
    # ----------------------------------------------------
    constraints = scene.get("constraints", [])
    if isinstance(constraints, list):
        for c_idx, constraint in enumerate(constraints):
            if isinstance(constraint, dict):
                c_objects = constraint.get("objects", [])
                if isinstance(c_objects, list):
                    for obj in c_objects:
                        if obj not in created_objects:
                            errors.append(f"Constraint {c_idx} ({constraint.get('type', 'unknown')}): Referenced object '{obj}' does not exist")

    # ----------------------------------------------------
    # 8. Expected Count Checks from validation block
    # ----------------------------------------------------
    validation_block = scene.get("validation", {})
    if isinstance(validation_block, dict):
        expected_op_count = validation_block.get("expected_operation_count")
        if expected_op_count is not None and isinstance(expected_op_count, int):
            if len(operations) != expected_op_count:
                errors.append(f"Validation count mismatch: expected_operation_count is {expected_op_count}, but scene has {len(operations)} operations")

        expected_obj_count = validation_block.get("expected_object_count")
        if expected_obj_count is not None and isinstance(expected_obj_count, int):
            if len(created_objects) != expected_obj_count:
                errors.append(f"Validation count mismatch: expected_object_count is {expected_obj_count}, but {len(created_objects)} objects were created ({sorted(created_objects)})")

    return errors
