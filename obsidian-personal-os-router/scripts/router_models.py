#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TASK_MODEL_DIR = SCRIPT_DIR.parents[1] / "obsidian-planetary-tasks-manager" / "scripts"
if str(TASK_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_MODEL_DIR))

from task_models import DependencyStatus, ReadBudget, RouteOutput, RouteSpec  # noqa: E402

__all__ = ["DependencyStatus", "ReadBudget", "RouteOutput", "RouteSpec"]
