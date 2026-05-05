#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from workflow_metrics import emit_execution_transition_metrics
from workflow_lib import DEFAULT_STATE_PATH, load_state, next_stop_decision, save_state


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return 0

    try:
        state = load_state(DEFAULT_STATE_PATH)
    except Exception as exc:
        print(json.dumps({"systemMessage": f"workflow hook ignored invalid state: {exc}"}))
        return 0

    if state is None:
        return 0

    previous_status = state["workflow_status"]
    state, decision, changed = next_stop_decision(state)
    if changed:
        save_state(state, DEFAULT_STATE_PATH)
        emit_execution_transition_metrics(
            state,
            previous_status=previous_status,
            source="stop_hook",
        )

    if decision.action in {"block", "escalate"} and decision.prompt:
        print(json.dumps({"decision": "block", "reason": decision.prompt}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
