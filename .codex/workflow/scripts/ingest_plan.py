#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow_lib import (
    DEFAULT_BASE_BRANCH,
    DEFAULT_REVIEW_PATH,
    DEFAULT_SHIP_SKILL,
    DEFAULT_STATE_PATH,
    build_state_from_plan_spec,
    load_plan_spec,
    save_state,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the live Codex workflow state from an approved plan artifact."
    )
    parser.add_argument("source", type=Path, help="Path to a JSON plan file or markdown file containing a plan block.")
    parser.add_argument("--plan-id", help="Select one plan when the source contains multiple plan specs.")
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH, help="Destination for the live workflow state.")
    parser.add_argument("--mode", choices=["stepwise", "ship"], default="ship", help="Fallback mode when the plan omits one.")
    parser.add_argument("--base-branch", default=DEFAULT_BASE_BRANCH, help="Fallback base branch when the plan omits one.")
    parser.add_argument("--review-path", default=DEFAULT_REVIEW_PATH, help="Fallback review policy path when the plan omits one.")
    parser.add_argument("--ship-skill", default=DEFAULT_SHIP_SKILL, help="Fallback ship skill when the plan omits one.")
    parser.add_argument(
        "--request-codex-review",
        dest="request_codex_review",
        action="store_true",
        default=True,
        help="Request `@codex review` after PR creation unless the plan overrides it.",
    )
    parser.add_argument(
        "--no-request-codex-review",
        dest="request_codex_review",
        action="store_false",
        help="Do not request `@codex review` after PR creation unless the plan overrides it.",
    )
    parser.add_argument("--print", action="store_true", help="Print the generated state JSON after writing it.")
    args = parser.parse_args()

    plan_spec = load_plan_spec(args.source, plan_id=args.plan_id)
    state = build_state_from_plan_spec(
        plan_spec,
        plan_path=_relative_or_source(args.source),
        review_path=args.review_path,
        ship_skill=args.ship_skill,
        base_branch=args.base_branch,
        mode=args.mode,
        request_codex_review=args.request_codex_review,
    )
    save_state(state, args.state_path)

    print(f"workflow state created at {args.state_path}")
    print(f"workflow: {state['workflow_name']}")
    print(f"current step: {state['current_step_id']}")
    if args.print:
        print(json.dumps(state, indent=2))
    return 0


def _relative_or_source(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
