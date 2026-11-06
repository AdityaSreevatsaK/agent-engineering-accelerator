"""Create CI-ONLY synthetic calculator inputs for metadata-contract tests.

The calculator agent and dataset were restored from the uploaded recording and
screenshot on 6 November. CI now verifies those reconstructions directly and
does NOT invoke this legacy stand-in generator. The existing hard refusal to
overwrite real source files is retained for safety. Synthetic stand-ins must
never be presented as originals or committed to the repository.
"""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dest = root / "examples" / "calculator"
    agent_path = dest / "agent.py"
    dataset_path = dest / "dataset.jsonl"

    if agent_path.exists() or dataset_path.exists():
        raise SystemExit(
            "Refusing to replace existing example files; verify originals directly instead."
        )

    dest.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(
        '"""CI-only synthetic placeholder, not original AEA calculator code."""\n'
        "def build_agent():\n"
        '    raise RuntimeError("Synthetic calculator agent must not be invoked")\n',
        encoding="utf-8",
    )
    dataset_path.write_text(
        json.dumps({"id": "synthetic-only", "input": "CI provenance test placeholder"})
        + "\n",
        encoding="utf-8",
    )

    print("Created temporary SYNTHETIC calculator dataset and agent stub for metadata tests.")
    print("Not original reconstruction; generated CI files must not be committed.")


if __name__ == "__main__":
    main()
