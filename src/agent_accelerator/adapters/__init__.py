"""Framework adapters. Each adapter is an Inspect solver that runs one case and records into
state.metadata: "tool_calls" (list of {"name", "arguments"}), "tool_errors" (per call: True if its result
was an error, None if no result arrived), "agent_error" (str or None),
"usage" (token counts, or None when the provider reported none) and "model_id".
"""

import importlib
from collections.abc import Callable
from typing import Any


def load_factory(ref: str) -> Callable[[], Any]:
    """Resolve "package.module:function" to the agent factory it names."""
    module_name, sep, attr = ref.partition(":")
    if not sep or not module_name or not attr:
        raise ValueError(f"agent reference must look like 'module:function', got {ref!r}")
    factory = getattr(importlib.import_module(module_name), attr, None)
    if factory is None:
        raise ValueError(f"{module_name} has no attribute {attr!r}")
    if not callable(factory):
        raise ValueError(f"{ref} is not callable")
    return factory
