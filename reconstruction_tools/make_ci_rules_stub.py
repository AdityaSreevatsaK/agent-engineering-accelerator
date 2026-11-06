"""Write a disposable CI-only import shim for the still-missing original rules.py.

The recovered calculator agent imports examples.calculator.rules at module import
time. Metadata tests only load its factory, so they need the symbols to exist but
must NOT execute invented rules. Every shim operation raises if called.

NEVER commit generated examples/calculator/rules.py as historical source.
Once the original rules.py is restored, this helper leaves it untouched.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "examples" / "calculator" / "rules.py"

SHIM = '''"""CI-ONLY NON-EXECUTABLE SHIM. NOT THE HISTORICAL CALCULATOR RULES."""

from dataclasses import dataclass


OPERATIONS: dict[str, str] = {}
BROKEN_OPERATIONS: dict[str, str] = {}
SYSTEM_PROMPT = "CI-only import shim; never execute this model."


@dataclass
class ToolRequest:
    arguments: dict


def _not_available(*args, **kwargs):
    raise RuntimeError("Historical calculator rules.py is missing: CI shim cannot execute")


def answer(*args, **kwargs):
    return _not_available(*args, **kwargs)


def calculate(*args, **kwargs):
    return _not_available(*args, **kwargs)


def decide(*args, **kwargs):
    return _not_available(*args, **kwargs)
'''


def main() -> None:
    if DEST.exists():
        # Do not overwrite original source when the user provides it.
        print("Calculator rules.py exists; original module is preserved unchanged.")
        return
    if not (DEST.parent / "agent.py").is_file():
        raise RuntimeError("Recovered agent.py missing; refusing to create a misleading rules shim")
    DEST.write_text(SHIM, encoding="utf-8")
    print("Created NON-EXECUTABLE CI-only rules import shim; not an original file.")
    print("Safe for metadata-only tests; genuine calculator agent execution remains blocked.")


if __name__ == "__main__":
    main()
