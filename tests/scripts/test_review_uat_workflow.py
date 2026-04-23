from __future__ import annotations

import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path


TESTS_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(TESTS_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_SCRIPTS_DIR))

from workflow_test_support import (  # noqa: E402
    STATE_EXAMPLE_PATH,
    example_plan,
    load_workflow_lib,
    load_workflow_router_lib,
    rebase_execution_state_paths,
    run_workflow_state_command,
    save_example_uat_artifact,
)


def _build_execution_state(workflow_lib, tmpdir: str) -> dict:
    return rebase_execution_state_paths(
        workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md"),
        tmpdir,
    )


def test_review_pending_step_blocks_for_review_gate():
    workflow_lib = load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["steps"][0]["status"] = "review_pending"

    _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert decision.action == "block"
    assert "code_review.md" in decision.prompt
    assert "python3 .codex/workflow/scripts/workflow_state.py set-step-status step-1 commit_pending" in decision.prompt
    assert "set-step-status step-1 commit_pending" in decision.prompt


def test_workflow_state_review_pending_requires_pre_review_sensors():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["verify_cmds"] = []
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "deterministic pre-review sensors" in result.stderr
    assert persisted_state["workflow_status"] == "execution_escalated"
    assert persisted_state["steps"][0]["status"] == "implementing"
    assert persisted_state["escalation"]["code"] == "verification_missing"


def test_final_committed_step_enters_uat_pending_mode():
    workflow_lib = load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["current_step_id"] = "step-2"
    state["steps"][0]["status"] = "committed"
    state["steps"][1]["status"] = "committed"
    state["uat_artifact_path"] = str(STATE_EXAMPLE_PATH.parent / "uat.json")

    new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert new_state["workflow_status"] == "uat_pending"
    assert decision.action == "block"
    assert "set-uat-status passed" in decision.prompt


def test_uat_pending_blocks_with_uat_prompt():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        save_example_uat_artifact(workflow_lib, state)

        _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert "user-acceptance gate" in decision.prompt
    assert "set-uat-status failed-gap" in decision.prompt


def test_gap_closure_pending_returns_to_uat_after_fix_commit():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "gap_closure_pending"
        state["steps"][0]["status"] = "committed"
        save_example_uat_artifact(workflow_lib, state)

        new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert new_state["workflow_status"] == "uat_pending"
    assert "set-uat-status passed" in decision.prompt


def test_replan_required_blocks_with_follow_up_planning_prompt():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "replan_required"
        state["steps"][0]["status"] = "committed"
        save_example_uat_artifact(workflow_lib, state)
        workflow_lib.update_uat_artifact_result(
            Path(state["uat_artifact_path"]),
            "failed_replan",
            "The approved architecture no longer matches the required scope.",
        )

        _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert "cannot ship" in decision.prompt
    assert "follow-up planning session" in decision.prompt


def test_workflow_state_set_step_status_review_transitions_persist_state():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        workflow_lib.save_state(state, state_path)

        review_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        state_after_review = workflow_lib.load_state(state_path)

        fix_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "fix_pending",
            "--review-summary",
            "Missing regression assertion.",
        )
        state_after_fix = workflow_lib.load_state(state_path)

        rereview_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        state_after_rereview = workflow_lib.load_state(state_path)

        pass_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            "--review-summary",
            "review passed",
        )
        state_after_pass = workflow_lib.load_state(state_path)

        commit_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "committed",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert review_result.returncode == 0, review_result.stderr
    assert state_after_review["steps"][0]["status"] == "review_pending"
    assert fix_result.returncode == 0, fix_result.stderr
    assert state_after_fix["steps"][0]["status"] == "fix_pending"
    assert state_after_fix["steps"][0]["review_summary"] == "Missing regression assertion."
    assert rereview_result.returncode == 0, rereview_result.stderr
    assert state_after_rereview["steps"][0]["status"] == "review_pending"
    assert pass_result.returncode == 0, pass_result.stderr
    assert state_after_pass["steps"][0]["status"] == "commit_pending"
    assert state_after_pass["steps"][0]["review_summary"] == "review passed"
    assert commit_result.returncode == 0, commit_result.stderr
    assert persisted_state["steps"][0]["status"] == "committed"


def test_resume_surfaces_execution_escalation_for_invalid_review_state():
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["status"] = "review_pending"
        state["steps"][0]["verify_cmds"] = []
        workflow_lib.save_state(state, state_path)

        response = workflow_router.resume_workflow(
            planning_state_path=planning_state_path,
            execution_state_path=state_path,
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert response.status == "ok"
    assert response.message == "workflow execution escalated"
    assert "verification_missing" in response.additional_context
    assert persisted_state["workflow_status"] == "execution_escalated"
    assert persisted_state["steps"][0]["status"] == "review_pending"
    assert persisted_state["escalation"]["code"] == "verification_missing"


def test_resolve_escalation_returns_workflow_to_active_execution():
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["verify_cmds"] = []
        workflow_lib.save_state(state, state_path)

        failed_review = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        escalated_state = workflow_lib.load_state(state_path)
        escalated_state["steps"][0]["verify_cmds"] = ["uv run pytest tests/ai/test_embedding_service.py"]
        workflow_lib.save_state(escalated_state, state_path)

        resolve_result = run_workflow_state_command(
            state_path,
            "resolve-escalation",
        )
        persisted_state = workflow_lib.load_state(state_path)
        response = workflow_router.resume_workflow(
            planning_state_path=planning_state_path,
            execution_state_path=state_path,
        )

    assert failed_review.returncode != 0
    assert resolve_result.returncode == 0, resolve_result.stderr
    assert persisted_state["workflow_status"] == "active"
    assert persisted_state["escalation"] is None
    assert "Start the next execution step." not in response.additional_context
    assert "Do not stop yet." in response.additional_context


def test_workflow_state_set_uat_status_passed_updates_state_and_artifact():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(workflow_lib, state)

        result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "passed",
            "--summary",
            "UAT passed cleanly.",
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "ship_pending"
    assert uat_artifact["overall_status"] == "passed"
    assert uat_artifact["summary"] == "UAT passed cleanly."


def test_workflow_state_set_uat_status_failed_gap_transitions_to_gap_closure():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(workflow_lib, state)

        result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "failed-gap",
            "--summary",
            "One fixable verification gap remains.",
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "gap_closure_pending"
    assert persisted_state["steps"][0]["status"] == "implementing"
    assert persisted_state["steps"][0]["review_summary"] == "One fixable verification gap remains."
    assert uat_artifact["overall_status"] == "failed_gap"


def test_workflow_state_set_uat_status_failed_replan_transitions_to_replan_required():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(workflow_lib, state)

        result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "failed-replan",
            "--summary",
            "The approved architecture no longer matches the needed scope.",
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "replan_required"
    assert uat_artifact["overall_status"] == "failed_replan"


def test_workflow_state_set_workflow_status_requires_override_reason_for_manual_change():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["status"] = "implementing"
        workflow_lib.save_state(state, state_path)

        missing_reason = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "uat_pending",
        )
        state_after_failure = workflow_lib.load_state(state_path)

        override_result = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "uat_pending",
            "--override-reason",
            "manual reconciliation for regression coverage",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert missing_reason.returncode != 0
    assert "manual override" in missing_reason.stderr
    assert state_after_failure["workflow_status"] == "active"
    assert override_result.returncode == 0, override_result.stderr
    assert persisted_state["workflow_status"] == "uat_pending"


def test_workflow_state_set_workflow_status_complete_requires_ship_pending_and_shipped():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)

        wrong_status = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "complete",
        )

        state["workflow_status"] = "ship_pending"
        workflow_lib.save_state(state, state_path)
        not_shipped = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "complete",
        )
        persisted_state = workflow_lib.load_state(state_path)
        metrics_exists = (Path(state["metrics_dir"]) / "events.jsonl").exists()

    assert wrong_status.returncode != 0
    assert "ship_pending" in wrong_status.stderr
    assert not_shipped.returncode != 0
    assert "current step to be shipped" in not_shipped.stderr
    assert persisted_state["workflow_status"] == "ship_pending"
    assert metrics_exists is False


def test_next_stop_decision_escalates_shipped_state_inconsistency():
    workflow_lib = load_workflow_lib()
    state = workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md")
    state["steps"][0]["status"] = "shipped"

    next_state, decision, changed = workflow_lib.next_stop_decision(state)

    assert changed is True
    assert decision.action == "escalate"
    assert next_state["workflow_status"] == "execution_escalated"
    assert next_state["escalation"]["code"] == "manual_override"


def test_workflow_state_set_step_status_shipped_requires_ship_pending_and_committed():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        workflow_lib.save_state(state, state_path)

        wrong_status = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
        )

        state["workflow_status"] = "ship_pending"
        workflow_lib.save_state(state, state_path)
        not_committed = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert wrong_status.returncode != 0
    assert "workflow_status ship_pending" in wrong_status.stderr
    assert not_committed.returncode != 0
    assert "current step to be committed" in not_committed.stderr
    assert persisted_state["steps"][0]["status"] == "implementing"


def test_next_stop_decision_requires_explicit_completion_after_shipped_step():
    workflow_lib = load_workflow_lib()
    state = workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md")
    state["workflow_status"] = "ship_pending"
    state["steps"][0]["status"] = "shipped"

    next_state, decision, changed = workflow_lib.next_stop_decision(state)

    assert changed is False
    assert next_state["workflow_status"] == "ship_pending"
    assert decision.action == "block"
    assert "set-workflow-status complete" in (decision.prompt or "")
