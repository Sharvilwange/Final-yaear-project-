"""
config.py — Central configuration for the AI Procedural 3D system.

All model names are defined here as the single source of truth.
To swap a model, change it ONLY in this file.
"""

import os

# ------------------------------------------------------------------
# Model names
# ------------------------------------------------------------------

# Planner: DeepSeek-R1 7B (reasoning / step-planning)
PLANNER_MODEL = "deepseek-r1:7b"

# Builder: Qwen 2.5 (JSON-structured geometry generation)
BUILDER_MODEL = "qwen2.5:latest"

# Vision Validator: Qwen2.5-VL 3B (image + text validation)
# Can be overridden via the VISION_MODEL environment variable.
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen2.5vl:3b")

# Text-only fallback validator (used when no rendered image is available)
# Can be overridden via the TEXT_VALIDATOR_MODEL environment variable.
TEXT_VALIDATOR_MODEL = os.environ.get("TEXT_VALIDATOR_MODEL", "deepseek-r1:7b")
