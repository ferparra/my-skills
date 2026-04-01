#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

SCRIPT_DIR = Path(__file__).resolve().parent
TASK_MODEL_PATH = (
    SCRIPT_DIR.parent.parent
    / "obsidian-planetary-tasks-manager"
    / "scripts"
    / "task_models.py"
)


class _TaskModelsModule(Protocol):
    DependencyStatus: type["DependencyStatus"]
    ReadBudget: type["ReadBudget"]
    RouteOutput: type["RouteOutput"]
    RouteSpec: type["RouteSpec"]


def _load_task_models() -> _TaskModelsModule:
    existing_module = sys.modules.get("_router_task_models")
    if existing_module is not None:
        return cast(_TaskModelsModule, existing_module)

    spec = importlib.util.spec_from_file_location("_router_task_models", TASK_MODEL_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load task models from {TASK_MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(_TaskModelsModule, module)


if TYPE_CHECKING:
    from task_models import DependencyStatus, ReadBudget, RouteOutput, RouteSpec
else:
    _task_models = _load_task_models()
    DependencyStatus = _task_models.DependencyStatus
    ReadBudget = _task_models.ReadBudget
    RouteOutput = _task_models.RouteOutput
    RouteSpec = _task_models.RouteSpec

__all__ = ["DependencyStatus", "ReadBudget", "RouteOutput", "RouteSpec"]
