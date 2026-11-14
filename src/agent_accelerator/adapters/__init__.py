"""Framework adapters. Each adapter is an Inspect solver that runs one case and records into
state.metadata: "tool_calls" (list of {"name", "arguments"}), "tool_errors" (per call: True if its result
was an error, None if no result arrived), "agent_error" (str or None),
"usage" (token counts, or None when the provider reported none) and "model_id".
"""

import importlib
import keyword
from collections.abc import Callable
from typing import Any


def validate_factory_reference(ref: str) -> tuple[str, str]:
    """Validate a Python module:function reference without importing user code."""
    module_name, separator, attr = ref.partition(":")
    segments = module_name.split(".")
    if (
        not separator
        or not module_name
        or not attr
        or ":" in attr
        or any(not part.isidentifier() or keyword.iskeyword(part) for part in segments)
        or not attr.isidentifier()
        or keyword.iskeyword(attr)
    ):
        raise ValueError(f"reference must look like 'module:function' with valid Python names, got {ref!r}")
    return module_name, attr


def load_factory(ref: str) -> Callable[[], Any]:
    """Resolve "package.module:function" to a callable in the current import environment."""
    module_name, attr = validate_factory_reference(ref)
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        # Distinguish a misspelt application module from a missing transitive
        # dependency inside an existing agent module.
        if exc.name is not None and (module_name == exc.name or module_name.startswith(exc.name + ".")):
            raise ModuleNotFoundError(
                f"cannot import module {module_name!r}; check the working directory and module path",
                name=exc.name,
            ) from None
        raise
    factory = getattr(module, attr, None)
    if factory is None:
        raise ValueError(f"{module_name} has no attribute {attr!r}")
    if not callable(factory):
        raise ValueError(f"{ref} is not callable")
    return factory
