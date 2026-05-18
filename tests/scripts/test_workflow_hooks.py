from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path


TESTS_SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / ".codex" / "workflow" / "scripts"
USER_PROMPT_HOOK_PATH = WORKFLOW_SCRIPTS_DIR / "user_prompt_hook.py"
STOP_HOOK_PATH = WORKFLOW_SCRIPTS_DIR / "stop_hook.py"


if str(TESTS_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_SCRIPTS_DIR))
if str(WORKFLOW_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS_DIR))


from workflow_test_support import (  # noqa: E402
    example_plan,
    load_module,
    load_workflow_lib,
    load_workflow_router_lib,
    rebase_execution_state_paths,
)


def _load_user_prompt_hook():
    return load_module("codex_user_prompt_hook_test", USER_PROMPT_HOOK_PATH)


def _load_stop_hook():
    return load_module("codex_stop_hook_test", STOP_HOOK_PATH)


def test_user_prompt_hook_parses_workflow_start_command():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_activation_request(
        "/workflow start PLANS.md --plan-id phase-1 --mode stepwise --base-branch origin/develop --no-request-codex-review"
    )

    assert request is not None
    assert str(request.source) == "PLANS.md"
    assert request.plan_id == "phase-1"
    assert request.mode == "stepwise"
    assert request.base_branch == "origin/develop"
    assert request.request_codex_review is False


def test_user_prompt_hook_parses_planning_request():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("/workflow add a planning phase for feature delivery")

    assert request is not None
    assert request.action == "start_planning"
    assert request.feature_request == "add a planning phase for feature delivery"


def test_user_prompt_hook_parses_bootstrap_request():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("/workflow bootstrap build a new greenfield workflow kernel")

    assert request is not None
    assert request.action == "start_bootstrap"
    assert request.feature_request == "build a new greenfield workflow kernel"


def test_user_prompt_hook_parses_revise_request():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("/workflow revise simplify the step breakdown")

    assert request is not None
    assert request.action == "revise_planning"
    assert request.feedback == "simplify the step breakdown"


def test_user_prompt_hook_blocks_execution_activation_while_planning_exists():
    workflow_router = load_workflow_router_lib()
    user_prompt_hook = _load_user_prompt_hook()
    plan = example_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow_root = Path(tmpdir) / ".codex" / "workflow"
        planning_state_path = workflow_root / "planning_state.json"
        execution_state_path = workflow_root / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        workflow_router.start_planning(
            "Plan a legacy hook guard",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        request = user_prompt_hook.parse_workflow_request(f"/workflow start {plan_path}")
        assert request is not None

        original_planning_state_path = user_prompt_hook.DEFAULT_PLANNING_STATE_PATH
        original_execution_state_path = user_prompt_hook.DEFAULT_STATE_PATH
        stdout = io.StringIO()
        try:
            user_prompt_hook.DEFAULT_PLANNING_STATE_PATH = planning_state_path
            user_prompt_hook.DEFAULT_STATE_PATH = execution_state_path
            with contextlib.redirect_stdout(stdout):
                result_code = user_prompt_hook._handle_execution_activation(request)
        finally:
            user_prompt_hook.DEFAULT_PLANNING_STATE_PATH = original_planning_state_path
            user_prompt_hook.DEFAULT_STATE_PATH = original_execution_state_path

    assert result_code == 0
    payload = json.loads(stdout.getvalue())
    assert "blocked" in payload["systemMessage"]
    assert "planning-approve" in payload["hookSpecificOutput"]["additionalContext"]


def test_stop_hook_emits_escalation_metrics_for_legacy_execution_path(monkeypatch):
    workflow_lib = load_workflow_lib()
    stop_hook = _load_stop_hook()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["steps"][0]["status"] = "review_pending"
        state["steps"][0]["verify_cmds"] = []
        workflow_lib.save_state(state, state_path)

        stdout = io.StringIO()
        original_state_path = stop_hook.DEFAULT_STATE_PATH
        try:
            stop_hook.DEFAULT_STATE_PATH = state_path
            monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
            with contextlib.redirect_stdout(stdout):
                result_code = stop_hook.main()
        finally:
            stop_hook.DEFAULT_STATE_PATH = original_state_path

        persisted_state = workflow_lib.load_state(state_path)
        events = [
            json.loads(line)
            for line in (Path(state["metrics_dir"]) / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        scorecard = json.loads((Path(state["metrics_dir"]) / "scorecard.json").read_text(encoding="utf-8"))

    assert result_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["decision"] == "block"
    assert persisted_state["workflow_status"] == "execution_escalated"
    assert persisted_state["escalation"]["code"] == "verification_missing"
    assert [event["event"] for event in events] == [
        "deterministic_sensor_failed",
        "execution_escalation_entered",
    ]
    assert events[0]["category"] == "verification_missing"
    assert events[0]["source"] == "stop_hook"
    assert events[1]["category"] == "verification_missing"
    assert scorecard["counts"]["deterministic_sensor_failed"] == 1
    assert scorecard["counts"]["execution_escalation_entered"] == 1


def test_user_prompt_hook_ignores_normal_prompts():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("implement the approved plan")

    assert request is None
