#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    # Keep the caller's cwd so repo-local workflow state stays in the active project.
    target = Path(__file__).resolve().parents[4] / ".codex" / "workflow" / "scripts" / "planning_state.py"
    if not target.exists():
        raise SystemExit(f"bundled planning state tool not found: {target}")
    if str(target.parent) not in sys.path:
        sys.path.insert(0, str(target.parent))
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
